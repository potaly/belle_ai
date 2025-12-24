"""Vision analysis service (V6.0.0+).

核心业务逻辑：调用视觉模型，生成导购私聊话术。
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.schemas.vision import (
    GuideChatCopy,
    ResolverDebug,
    StructureSignals,
    Tracking,
    VisionAnalyzeData,
    VisionFeatures,
    VisualSummary,
)
from app.repositories.vision_feature_cache_repository import (
    VisionFeatureCacheRepository,
)
from app.services.brand_vocab_service import BrandVocabService
from app.services.category_resolver import CategoryResolver
from app.services.prompts.vision_prompts import (
    build_vision_analyze_prompts,
    build_vision_system_prompt,
    build_vision_user_prompt,
)
from app.services.vision_client import VisionClient, VisionClientError
from app.services.vision_enum_resolver import VisionEnumResolver
from app.services.vision_feature_normalizer import VisionFeatureNormalizer
from app.services.vision_validators import validate_vision_output

logger = logging.getLogger(__name__)


class VisionAnalyzeService:
    """Vision analysis service."""

    def __init__(self) -> None:
        self.vision_client = VisionClient()

    async def analyze(
        self,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        brand_code: str = "",
        scene: str = "guide_chat",
        db: Optional[Session] = None,
    ) -> VisionAnalyzeData:
        """
        分析图片并生成导购私聊话术。
        
        Args:
            image_url: 图片URL
            image_base64: 图片Base64编码
            brand_code: 品牌编码
        
        Returns:
            VisionAnalyzeData
        
        Raises:
            VisionClientError: 当视觉模型调用失败时
        """
        logger.info("=" * 80)
        logger.info("[VISION_SERVICE] ========== Vision Analysis ==========")
        logger.info(
            f"[VISION_SERVICE] Input: image_url={'provided' if image_url else 'none'}, "
            f"image_base64={'provided' if image_base64 else 'none'}, brand_code={brand_code}"
        )

        try:
            # Step 1: 获取品牌枚举约束（P4.x.1）
            allowed_enums = {}
            strategy_used = "llm_enum"
            
            if db and brand_code:
                try:
                    vocab_service = BrandVocabService(db)
                    allowed_enums = vocab_service.get_all_allowed_enums(brand_code)
                    logger.info(
                        f"[VISION_SERVICE] ✓ Loaded brand enums: "
                        f"categories={len(allowed_enums.get('categories', []))}, "
                        f"seasons={len(allowed_enums.get('seasons', []))}, "
                        f"styles={len(allowed_enums.get('styles', []))}, "
                        f"colors={len(allowed_enums.get('colors', []))}"
                    )
                except Exception as e:
                    logger.warning(
                        f"[VISION_SERVICE] Failed to load brand enums: {e}, "
                        f"will use fallback prompts"
                    )
                    allowed_enums = {}
                    strategy_used = "fallback_rule"

            # Step 2: 构建 prompt（使用枚举约束或降级到旧版本）
            logger.info("[VISION_SERVICE] Step 2: Building prompts...")
            if allowed_enums.get("categories"):
                # 使用新的枚举约束 prompt
                system_prompt, user_prompt = build_vision_analyze_prompts(
                    image_url_or_bytes=image_url or image_base64 or "",
                    brand_no=brand_code,
                    scene=scene,
                    allowed_enums=allowed_enums,
                )
                logger.info("[VISION_SERVICE] ✓ Enum-constrained prompts built")
            else:
                # 降级到旧版本 prompt（向后兼容）
                system_prompt = build_vision_system_prompt()
                user_prompt = build_vision_user_prompt(
                    image_url=image_url or image_base64 or "",
                    brand_code=brand_code,
                )
                logger.info("[VISION_SERVICE] ✓ Fallback prompts built")

            # Step 3: 调用视觉模型
            logger.info("[VISION_SERVICE] Step 3: Calling vision model...")
            raw_result = await self.vision_client.analyze_image(
                image_url=image_url,
                image_base64=image_base64,
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            logger.info(f"[VISION_SERVICE] ✓ Vision model response received: {json.dumps(raw_result, ensure_ascii=False)[:200]}")

            # Step 4: 解析和验证输出
            logger.info("[VISION_SERVICE] Step 4: Parsing and validating output...")
            
            # 尝试解析 JSON（如果使用枚举约束 prompt，VLM 应该返回严格 JSON）
            parsed_result = raw_result
            if isinstance(raw_result, str):
                try:
                    parsed_result = json.loads(raw_result)
                except json.JSONDecodeError:
                    logger.warning(
                        "[VISION_SERVICE] VLM output is not JSON, attempting extraction..."
                    )
                    # 尝试从文本中提取 JSON
                    parsed_result = self._extract_json_from_text(raw_result)
            
            # 应用枚举约束和规则兜底（如果使用了枚举约束）
            corrections = []
            if allowed_enums.get("categories"):
                try:
                    parsed_result, corrections = VisionEnumResolver.resolve_with_fallback(
                        vlm_output=parsed_result,
                        allowed_enums=allowed_enums,
                        brand_no=brand_code,
                    )
                    if corrections:
                        logger.info(
                            f"[VISION_SERVICE] ✓ Applied enum constraints with corrections: {corrections}"
                        )
                    else:
                        logger.info("[VISION_SERVICE] ✓ Enum constraints validated (no corrections needed)")
                except Exception as e:
                    logger.warning(
                        f"[VISION_SERVICE] Enum resolver failed: {e}, using raw output"
                    )
                    strategy_used = "fallback_rule"
            
            # 转换格式（如果使用枚举约束格式，需要转换为旧格式以兼容 validate_vision_output）
            if allowed_enums.get("categories") and "visual_summary" not in parsed_result:
                # 新格式：直接包含 category/season/style/color
                # 转换为旧格式：包含 visual_summary
                parsed_result = {
                    "visual_summary": {
                        "category_guess": parsed_result.get("category", "未知"),
                        "style_impression": parsed_result.get("style", []),
                        "color_impression": parsed_result.get("color", "未知"),
                        "season_impression": parsed_result.get("season", "四季"),
                        "confidence_note": parsed_result.get("confidence_note", "基于图片外观判断，可能存在误差"),
                    },
                    "selling_points": parsed_result.get("selling_points", []),
                    "guide_chat_copy": parsed_result.get("guide_chat_copy", {}),
                    "confidence_level": parsed_result.get("confidence", "medium"),
                    "structure_signals": parsed_result.get("structure_signals", {}),
                    # 保留原始字段用于后续处理
                    "category": parsed_result.get("category"),
                    "season": parsed_result.get("season"),
                    "style": parsed_result.get("style"),
                    "color": parsed_result.get("color"),
                    "colors": parsed_result.get("colors", []),
                    "category_guess_raw": parsed_result.get("category"),
                    "season_impression_raw": parsed_result.get("season"),
                    "style_impression_raw": parsed_result.get("style"),
                    "color_impression_raw": parsed_result.get("color"),
                }
            
            # 验证输出（兼容旧版本）
            validated_result = validate_vision_output(parsed_result)
            logger.info("[VISION_SERVICE] ✓ Output validated")

            # Step 5: 构建响应数据
            logger.info("[VISION_SERVICE] Step 5: Building response data...")
            data = self._build_response_data(
                validated_result,
                brand_code,
                scene,
                db,
                allowed_enums=allowed_enums,
                strategy_used=strategy_used,
                corrections=corrections,
            )
            logger.info("[VISION_SERVICE] ✓ Response data built")
            logger.info("=" * 80)

            return data

        except VisionClientError as e:
            logger.error(f"[VISION_SERVICE] ✗ Vision client error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[VISION_SERVICE] ✗ Unexpected error: {e}", exc_info=True)
            raise VisionClientError(f"Vision analysis failed: {str(e)}") from e

    def _extract_json_from_text(self, text: str) -> Dict:
        """
        从文本中提取 JSON（如果 VLM 返回了额外文本）。
        
        Args:
            text: VLM 返回的文本
        
        Returns:
            解析后的 JSON 字典
        """
        import re

        # 尝试提取 JSON 代码块
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))

        # 尝试提取第一个 JSON 对象
        json_match = re.search(r"\{.*\}", text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        # 如果都失败，返回原始文本（会被 validate_vision_output 处理）
        logger.warning("[VISION_SERVICE] Failed to extract JSON from text, using raw text")
        return {"raw_text": text}

    def _build_response_data(
        self,
        validated_result: Dict,
        brand_code: str,
        scene: str,
        db: Optional[Session] = None,
        allowed_enums: Optional[Dict] = None,
        strategy_used: str = "llm_enum",
        corrections: Optional[List[str]] = None,
    ) -> VisionAnalyzeData:
        """构建响应数据。"""
        # 提取 visual_summary（支持 raw/normalized 字段）
        visual_summary_data = validated_result.get("visual_summary", {})
        if not visual_summary_data:
            # 如果 VLM 直接返回了 category/season/style/color（枚举约束格式）
            visual_summary_data = {
                "category_guess": validated_result.get("category", "未知"),
                "category_guess_raw": validated_result.get("category_guess_raw"),
                "season_impression": validated_result.get("season", "四季"),
                "season_impression_raw": validated_result.get("season_impression_raw"),
                "style_impression": validated_result.get("style", []),
                "style_impression_raw": validated_result.get("style_impression_raw"),
                "color_impression": validated_result.get("color", "未知"),
                "color_impression_raw": validated_result.get("color_impression_raw"),
            }

        visual_summary = VisualSummary(
            category_guess_raw=visual_summary_data.get("category_guess_raw")
            or validated_result.get("category_guess_raw"),
            category_guess=visual_summary_data.get("category_guess")
            or validated_result.get("category", "未知"),
            style_impression_raw=visual_summary_data.get("style_impression_raw")
            or validated_result.get("style_impression_raw"),
            style_impression=visual_summary_data.get("style_impression")
            or validated_result.get("style", []),
            color_impression_raw=visual_summary_data.get("color_impression_raw")
            or validated_result.get("color_impression_raw"),
            color_impression=visual_summary_data.get("color_impression")
            or validated_result.get("color", "未知"),
            season_impression_raw=visual_summary_data.get("season_impression_raw")
            or validated_result.get("season_impression_raw"),
            season_impression=visual_summary_data.get("season_impression")
            or validated_result.get("season", "四季"),
            confidence_note=visual_summary_data.get("confidence_note")
            or validated_result.get("confidence_note", "基于图片外观判断，可能存在误差"),
        )

        # 提取 structure_signals（P4.x.1）
        structure_signals_data = validated_result.get("structure_signals", {})
        structure_signals = None
        if structure_signals_data:
            structure_signals = StructureSignals(
                open_heel=structure_signals_data.get("open_heel", False),
                open_toe=structure_signals_data.get("open_toe", False),
                heel_height=structure_signals_data.get("heel_height", "unknown"),
                toe_shape=structure_signals_data.get("toe_shape", "unknown"),
            )

        # 提取 selling_points
        selling_points = validated_result.get("selling_points", [])

        # 提取 guide_chat_copy
        guide_chat_copy_data = validated_result.get("guide_chat_copy", {})
        alternatives = guide_chat_copy_data.get("alternatives", [])
        
        # 确保 alternatives 至少3条（在创建对象之前）
        if len(alternatives) < 3:
            logger.warning(
                f"[VISION_SERVICE] Alternatives count < 3 ({len(alternatives)}), adding fallback alternatives"
            )
            fallback_alternatives = [
                "这款整体偏日常，穿着不会太累脚，你平时穿运动鞋多吗？",
                "这双风格比较休闲，搭牛仔裤也挺合适的",
                "从外观看感觉比较轻便，你平时更看重舒适度还是搭配？",
            ]
            alternatives.extend(
                fallback_alternatives[: 3 - len(alternatives)]
            )
        
        guide_chat_copy = GuideChatCopy(
            primary=guide_chat_copy_data.get("primary", "这双看起来不错，你平时穿什么码？"),
            alternatives=alternatives,
        )

        # 提取 confidence_level
        confidence_level = validated_result.get("confidence_level", "medium")

        # 构建 tracking
        tracking = Tracking(
            vision_used=True,
            confidence_level=confidence_level,
        )

        # Step 5: 归一化视觉特征（使用 Category Resolver）
        logger.info("[VISION_SERVICE] Step 5: Normalizing vision features...")
        
        # 创建 Category Resolver（如果提供了 db）
        category_resolver = None
        if db and brand_code:
            try:
                category_resolver = CategoryResolver(db)
                logger.info("[VISION_SERVICE] ✓ Category Resolver initialized")
            except Exception as e:
                logger.warning(f"[VISION_SERVICE] Failed to initialize Category Resolver: {e}, using fallback")
        
        vision_features_dict = VisionFeatureNormalizer.normalize(
            visual_summary={
                "category_guess": visual_summary.category_guess,
                "style_impression": visual_summary.style_impression,
                "color_impression": visual_summary.color_impression,
                "season_impression": visual_summary.season_impression,
            },
            selling_points=selling_points,
            brand_code=brand_code,
            scene=scene,
            category_resolver=category_resolver,
        )
        vision_features = VisionFeatures(**vision_features_dict)
        logger.info("[VISION_SERVICE] ✓ Vision features normalized")

        # Step 6: 生成 trace_id
        trace_id = VisionFeatureCacheRepository.generate_trace_id()
        logger.info(f"[VISION_SERVICE] ✓ Trace ID generated: {trace_id}")

        # Step 7: 构建 resolver_debug（P4.x.1）
        resolver_debug = None
        if allowed_enums:
            resolver_debug = ResolverDebug(
                brand_no=brand_code,
                allowed_categories_count=len(allowed_enums.get("categories", [])),
                allowed_styles_count=len(allowed_enums.get("styles", [])),
                allowed_seasons_count=len(allowed_enums.get("seasons", [])),
                allowed_colors_count=len(allowed_enums.get("colors", [])),
                strategy_used=strategy_used,
                corrections=corrections or [],
            )

        # 结构化日志
        logger.info(
            f"[VISION_SERVICE] ========== Vision Analysis Summary =========="
        )
        logger.info(f"[VISION_SERVICE] trace_id={trace_id}")
        logger.info(f"[VISION_SERVICE] brand_no={brand_code}")
        logger.info(
            f"[VISION_SERVICE] category_raw={visual_summary.category_guess_raw}, "
            f"category_normalized={visual_summary.category_guess}"
        )
        logger.info(
            f"[VISION_SERVICE] season_raw={visual_summary.season_impression_raw}, "
            f"season_normalized={visual_summary.season_impression}"
        )
        if corrections:
            logger.info(f"[VISION_SERVICE] corrections={corrections}")
        logger.info(f"[VISION_SERVICE] ========================================")

        return VisionAnalyzeData(
            visual_summary=visual_summary,
            structure_signals=structure_signals,
            selling_points=selling_points,
            guide_chat_copy=guide_chat_copy,
            tracking=tracking,
            trace_id=trace_id,
            vision_features=vision_features,
            resolver_debug=resolver_debug,
        )


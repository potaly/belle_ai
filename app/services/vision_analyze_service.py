"""Vision analysis service (V6.0.0+).

核心业务逻辑：调用视觉模型，生成导购私聊话术。
"""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from app.schemas.vision import (
    GuideChatCopy,
    Tracking,
    VisionAnalyzeData,
    VisualSummary,
)
from app.services.prompts.vision_prompts import (
    build_vision_system_prompt,
    build_vision_user_prompt,
)
from app.services.vision_client import VisionClient, VisionClientError
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
            # Step 1: 构建 prompt
            logger.info("[VISION_SERVICE] Step 1: Building prompts...")
            system_prompt = build_vision_system_prompt()
            user_prompt = build_vision_user_prompt(
                image_url=image_url or image_base64 or "",
                brand_code=brand_code,
            )
            logger.info("[VISION_SERVICE] ✓ Prompts built")

            # Step 2: 调用视觉模型
            logger.info("[VISION_SERVICE] Step 2: Calling vision model...")
            raw_result = await self.vision_client.analyze_image(
                image_url=image_url,
                image_base64=image_base64,
                prompt=user_prompt,
                system_prompt=system_prompt,
            )
            logger.info(f"[VISION_SERVICE] ✓ Vision model response received: {json.dumps(raw_result, ensure_ascii=False)[:200]}")

            # Step 3: 验证输出
            logger.info("[VISION_SERVICE] Step 3: Validating output...")
            validated_result = validate_vision_output(raw_result)
            logger.info("[VISION_SERVICE] ✓ Output validated")

            # Step 4: 构建响应数据
            logger.info("[VISION_SERVICE] Step 4: Building response data...")
            data = self._build_response_data(validated_result)
            logger.info("[VISION_SERVICE] ✓ Response data built")
            logger.info("=" * 80)

            return data

        except VisionClientError as e:
            logger.error(f"[VISION_SERVICE] ✗ Vision client error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[VISION_SERVICE] ✗ Unexpected error: {e}", exc_info=True)
            raise VisionClientError(f"Vision analysis failed: {str(e)}") from e

    def _build_response_data(self, validated_result: Dict) -> VisionAnalyzeData:
        """构建响应数据。"""
        # 提取 visual_summary
        visual_summary = VisualSummary(
            category_guess=validated_result.get("visual_summary", {}).get("category_guess", "未知"),
            style_impression=validated_result.get("visual_summary", {}).get("style_impression", []),
            color_impression=validated_result.get("visual_summary", {}).get("color_impression", "未知"),
            season_impression=validated_result.get("visual_summary", {}).get("season_impression", "四季"),
            confidence_note=validated_result.get("visual_summary", {}).get(
                "confidence_note", "基于图片外观判断，可能存在误差"
            ),
        )

        # 提取 selling_points
        selling_points = validated_result.get("selling_points", [])

        # 提取 guide_chat_copy
        guide_chat_copy_data = validated_result.get("guide_chat_copy", {})
        guide_chat_copy = GuideChatCopy(
            primary=guide_chat_copy_data.get("primary", "这双看起来不错，你平时穿什么码？"),
            alternatives=guide_chat_copy_data.get("alternatives", []),
        )

        # 确保 alternatives 至少3条
        if len(guide_chat_copy.alternatives) < 3:
            logger.warning(
                f"[VISION_SERVICE] Alternatives count < 3, adding fallback alternatives"
            )
            fallback_alternatives = [
                "这款整体偏日常，穿着不会太累脚，你平时穿运动鞋多吗？",
                "这双风格比较休闲，搭牛仔裤也挺合适的",
                "从外观看感觉比较轻便，你平时更看重舒适度还是搭配？",
            ]
            guide_chat_copy.alternatives.extend(
                fallback_alternatives[: 3 - len(guide_chat_copy.alternatives)]
            )

        # 提取 confidence_level
        confidence_level = validated_result.get("confidence_level", "medium")

        # 构建 tracking
        tracking = Tracking(
            vision_used=True,
            confidence_level=confidence_level,
        )

        return VisionAnalyzeData(
            visual_summary=visual_summary,
            selling_points=selling_points,
            guide_chat_copy=guide_chat_copy,
            tracking=tracking,
        )


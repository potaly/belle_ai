"""Product copy generation service (V5.5.0+).

核心职责：
- 基于商品卖点生成话术候选
- 支持不同场景（guide_chat / moments / poster）
- 支持不同风格（natural / professional / friendly）
- 不涉及用户行为、意图分析
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from app.core.config import get_settings
from app.models.product import Product
from app.services.fallback_product_copy import generate_fallback_product_copy
from app.services.llm_client import LLMClientError, get_llm_client
from app.services.product_analysis_service import analyze_selling_points
from app.services.prompt_templates import (
    FORBIDDEN_MARKETING_WORDS,
    build_product_copy_system_prompt,
    build_product_copy_user_prompt,
    validate_copy_output,
)

logger = logging.getLogger(__name__)


@dataclass
class CopyCandidate:
    """Copy candidate with scene and style."""

    scene: str  # "guide_chat" | "moments" | "poster"
    style: str  # "natural" | "professional" | "friendly"
    message: str  # Generated copy


async def generate_product_copy(
    product: Product,
    scene: str = "guide_chat",
    style: str = "natural",
    max_length: int = 50,
) -> List[CopyCandidate]:
    """
    生成商品话术候选（基于卖点，不涉及用户行为）。
    
    业务规则：
    - 基于商品卖点生成
    - 支持不同场景和风格
    - 禁止营销词汇
    - 基于商品事实，不编造
    
    Args:
        product: Product instance
        scene: Target scene (guide_chat / moments / poster)
        style: Writing style (natural / professional / friendly)
        max_length: Maximum length (default 50)
    
    Returns:
        List of CopyCandidate (at least 2 items)
    """
    logger.info(
        f"[PRODUCT_COPY] Generating product copy: sku={product.sku}, "
        f"scene={scene}, style={style}, max_length={max_length}"
    )
    
    # Step 1: Analyze selling points
    selling_points = analyze_selling_points(product, use_llm=True)
    logger.info(f"[PRODUCT_COPY] Selling points: {len(selling_points)} points")
    
    # Step 2: Generate copy candidates
    candidates: List[CopyCandidate] = []
    llm_used = False
    
    try:
        llm_client = get_llm_client()
        if llm_client.settings.llm_api_key and llm_client.settings.llm_base_url:
            # Build prompts
            system_prompt = build_product_copy_system_prompt()
            user_prompt = build_product_copy_user_prompt(
                product=product,
                selling_points=selling_points,
                scene=scene,
                style=style,
                max_length=max_length,
            )
            
            logger.info("[PRODUCT_COPY] Calling LLM to generate copy...")
            
            full_response = ""
            async for chunk in llm_client.stream_chat(
                user_prompt,
                system=system_prompt,
                temperature=0.8,  # Higher temperature for diversity
                max_tokens=300,  # More tokens for multiple candidates
            ):
                if chunk:
                    full_response += chunk
            
            # Parse LLM response
            parsed_messages = _parse_llm_copy_response(full_response)
            
            # Validate and create candidates (V5.8.2+ - guide_chat 特殊验证)
            valid_count = 0
            for msg in parsed_messages:
                if scene == "guide_chat":
                    # guide_chat 使用特殊验证器
                    from app.services.message_validators import validate_guide_chat_message
                    
                    is_valid, error = validate_guide_chat_message(
                        message=msg,
                        current_sku=product.sku,
                        product_name=product.name,
                        max_length=max_length,
                        min_length=10,
                    )
                else:
                    # moments / poster 使用通用验证
                    is_valid, error = validate_copy_output(msg, max_length)
                
                if is_valid:
                    candidates.append(
                        CopyCandidate(
                            scene=scene,
                            style=style,
                            message=msg,
                        )
                    )
                    valid_count += 1
                    if valid_count >= 3:  # Max 3 candidates
                        break
            
            if valid_count >= 2:
                llm_used = True
                logger.info(f"[PRODUCT_COPY] ✓ LLM generated {valid_count} candidates")
            else:
                logger.warning(
                    f"[PRODUCT_COPY] LLM generated insufficient candidates ({valid_count}), "
                    f"falling back to templates"
                )
                
    except LLMClientError as e:
        logger.warning(f"[PRODUCT_COPY] ⚠ LLM error: {e}, falling back to templates")
    except Exception as e:
        logger.error(
            f"[PRODUCT_COPY] ✗ Unexpected error during LLM generation: {e}",
            exc_info=True,
        )
    
    # Step 3: Fallback to rule-based templates (V5.8.2+ - guide_chat 降级后仍需验证)
    if not candidates or not llm_used:
        logger.info("[PRODUCT_COPY] Using fallback templates...")
        fallback_messages = generate_fallback_product_copy(
            product=product,
            selling_points=selling_points,
            scene=scene,
            style=style,
            max_length=max_length,
        )
        
        # V5.8.2+ - guide_chat 降级后仍需验证
        if scene == "guide_chat":
            from app.services.message_validators import validate_guide_chat_message
            
            validated_messages = []
            for msg in fallback_messages:
                is_valid, error = validate_guide_chat_message(
                    message=msg,
                    current_sku=product.sku,
                    product_name=product.name,
                    max_length=max_length,
                    min_length=10,
                )
                if is_valid:
                    validated_messages.append(msg)
                else:
                    logger.warning(
                        f"[PRODUCT_COPY] Fallback copy validation failed: {error}"
                    )
            
            fallback_messages = validated_messages if validated_messages else fallback_messages
        
        for msg in fallback_messages:
            candidates.append(
                CopyCandidate(
                    scene=scene,
                    style=style,
                    message=msg,
                )
            )
        
        logger.info(f"[PRODUCT_COPY] ✓ Fallback generated {len(fallback_messages)} candidates")
    
    # Ensure at least 2 candidates
    if len(candidates) < 2:
        # Generate additional fallback candidates
        additional = generate_fallback_product_copy(
            product=product,
            selling_points=selling_points,
            scene=scene,
            style=style,
            max_length=max_length,
            count=2 - len(candidates),
        )
        for msg in additional:
            candidates.append(
                CopyCandidate(
                    scene=scene,
                    style=style,
                    message=msg,
                )
            )
    
    logger.info(f"[PRODUCT_COPY] ✓ Final candidates: {len(candidates)}")
    for i, candidate in enumerate(candidates, 1):
        logger.debug(f"[PRODUCT_COPY]   {i}. [{candidate.scene}/{candidate.style}] {candidate.message}")
    
    return candidates


def _parse_llm_copy_response(response: str) -> List[str]:
    """解析 LLM 响应，提取多条话术。"""
    # 按行分割，过滤空行
    lines = [line.strip() for line in response.split("\n") if line.strip()]
    
    # 过滤掉明显的非消息内容
    messages = []
    for line in lines:
        # 移除编号前缀
        cleaned = line
        if cleaned.startswith(("1.", "2.", "3.", "第一条：", "第二条：", "第三条：")):
            cleaned = cleaned.split("：", 1)[-1].strip()
            if cleaned.startswith(("1.", "2.", "3.")):
                cleaned = cleaned.split(".", 1)[-1].strip()
        
        # 检查禁止词汇
        if not any(word in cleaned for word in FORBIDDEN_MARKETING_WORDS):
            messages.append(cleaned)
    
    # 如果解析失败，至少返回第一条消息
    if not messages and lines:
        messages.append(lines[0])
    
    return messages[:3]  # 最多 3 条


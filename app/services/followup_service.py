"""Follow-up suggestion service for personalized user engagement."""
from __future__ import annotations

import json
import logging
from typing import Dict, Optional

from app.models.product import Product
from app.services.intent_engine import (
    INTENT_HIGH,
    INTENT_HESITATING,
    INTENT_LOW,
    INTENT_MEDIUM,
)
from app.services.llm_client import LLMClient, LLMClientError, get_llm_client

logger = logging.getLogger(__name__)

# Action types
ACTION_ASK_SIZE = "ask_size"
ACTION_SEND_COUPON = "send_coupon"
ACTION_EXPLAIN_BENEFITS = "explain_benefits"
ACTION_DO_NOT_DISTURB = "do_not_disturb"
ACTION_PASSIVE_MESSAGE = "passive_message"


async def generate_followup_suggestion(
    product: Product,
    summary: dict,
    intention_level: str,
) -> dict:
    """
    Generate personalized follow-up suggestion based on user intent and behavior.
    
    This function uses a hybrid approach:
    1. Rule-based action selection based on intent level
    2. LLM-generated personalized message (with rule-based fallback)
    
    Args:
        product: Product instance
        summary: Behavior summary dictionary (from intent analysis)
        intention_level: Intent level ("high", "medium", "low", "hesitating")
    
    Returns:
        dict with keys:
            - "suggested_action": str - Action type (e.g., "ask_size", "send_coupon")
            - "message": str - Personalized follow-up text
    
    Examples:
        >>> product = Product(sku="8WZ01CM1", name="舒适跑鞋", ...)
        >>> summary = {"visit_count": 2, "max_stay_seconds": 30, ...}
        >>> result = await generate_followup_suggestion(product, summary, "high")
        >>> result["suggested_action"]
        'ask_size'
        >>> result["message"]
        '您好！看到您对这款舒适跑鞋很感兴趣，需要我帮您推荐合适的尺码吗？'
    """
    logger.info("=" * 80)
    logger.info("[FOLLOWUP] ========== Follow-up Suggestion Generation Started ==========")
    logger.info(
        f"[FOLLOWUP] Product: {product.name} (SKU: {product.sku}), "
        f"Intent: {intention_level}"
    )
    
    # Step 1: Determine suggested action based on intent level
    suggested_action = _determine_action(intention_level, summary)
    logger.info(f"[FOLLOWUP] ✓ Suggested action: {suggested_action}")
    
    # Step 2: Generate message using LLM (with rule-based fallback)
    try:
        logger.info("[FOLLOWUP] Attempting to generate message using LLM...")
        message = await _generate_llm_message(
            product=product,
            summary=summary,
            intention_level=intention_level,
            suggested_action=suggested_action,
        )
        logger.info("[FOLLOWUP] ✓ LLM message generated successfully")
    except Exception as e:
        logger.warning(
            f"[FOLLOWUP] ✗ LLM generation failed: {e}, falling back to rule-based message"
        )
        message = _generate_rule_based_message(
            product=product,
            summary=summary,
            intention_level=intention_level,
            suggested_action=suggested_action,
        )
        logger.info("[FOLLOWUP] ✓ Rule-based fallback message generated")
    
    result = {
        "suggested_action": suggested_action,
        "message": message,
    }
    
    logger.info(f"[FOLLOWUP] Final result: action={suggested_action}, message_length={len(message)}")
    logger.info("[FOLLOWUP] ========== Follow-up Suggestion Generation Completed ==========")
    logger.info("=" * 80)
    
    return result


def _determine_action(intention_level: str, summary: dict) -> str:
    """
    Determine suggested action based on intent level and behavior summary.
    
    Rules:
    - high → "ask_size" (Ask if they need size recommendation)
    - medium → "send_coupon" (Send limited-time coupon)
    - hesitating → "explain_benefits" (Explain product benefits + soft nudge)
    - low → "do_not_disturb" or "passive_message" (Do not disturb; optionally send passive-friendly message)
    
    Args:
        intention_level: Intent level string
        summary: Behavior summary dictionary
    
    Returns:
        str: Suggested action type
    """
    if intention_level == INTENT_HIGH:
        return ACTION_ASK_SIZE
    elif intention_level == INTENT_MEDIUM:
        return ACTION_SEND_COUPON
    elif intention_level == INTENT_HESITATING:
        return ACTION_EXPLAIN_BENEFITS
    elif intention_level == INTENT_LOW:
        # For low intent, we can optionally send a passive message
        # or choose not to disturb at all
        # Here we choose passive_message to maintain engagement
        return ACTION_PASSIVE_MESSAGE
    else:
        # Unknown intent level, default to passive message
        logger.warning(f"[FOLLOWUP] Unknown intent level: {intention_level}, defaulting to passive_message")
        return ACTION_PASSIVE_MESSAGE


async def _generate_llm_message(
    product: Product,
    summary: dict,
    intention_level: str,
    suggested_action: str,
) -> str:
    """
    Generate personalized follow-up message using LLM.
    
    Args:
        product: Product instance
        summary: Behavior summary dictionary
        intention_level: Intent level string
        suggested_action: Suggested action type
    
    Returns:
        str: Generated message
    
    Raises:
        LLMClientError: If LLM generation fails
    """
    # Build prompt with all required information
    prompt = _build_llm_prompt(product, summary, intention_level, suggested_action)
    
    # Get LLM client
    llm_client = get_llm_client()
    
    # System prompt for follow-up message generation
    system_prompt = (
        "你是一个专业的鞋类销售顾问，擅长根据用户的购买意图和行为数据，"
        "生成个性化、友好、不打扰的跟进消息。你的消息应该："
        "1. 简洁明了（不超过50字）"
        "2. 针对性强（根据意图级别和用户行为）"
        "3. 友好自然（不要过于推销）"
        "4. 提供价值（帮助用户做决定）"
    )
    
    try:
        # Use synchronous generate method for follow-up messages
        # (follow-up messages are typically short and don't need streaming)
        message = llm_client.generate(
            prompt=prompt,
            system=system_prompt,
            temperature=0.7,
            max_tokens=150,
        )
        
        # Clean up the message (remove any extra formatting)
        message = message.strip()
        
        # Validate message length (should be reasonable)
        if len(message) > 200:
            logger.warning(
                f"[FOLLOWUP] LLM generated message is too long ({len(message)} chars), truncating"
            )
            message = message[:200] + "..."
        
        return message
        
    except LLMClientError as e:
        logger.error(f"[FOLLOWUP] LLM client error: {e}")
        raise
    except Exception as e:
        logger.error(f"[FOLLOWUP] Unexpected error during LLM generation: {e}", exc_info=True)
        raise LLMClientError(f"Failed to generate LLM message: {e}") from e


def _build_llm_prompt(
    product: Product,
    summary: dict,
    intention_level: str,
    suggested_action: str,
) -> str:
    """
    Build prompt for LLM message generation.
    
    The prompt must include:
    - Product information
    - Behavior summary
    - Intention level
    - Action suggestion
    
    Args:
        product: Product instance
        summary: Behavior summary dictionary
        intention_level: Intent level string
        suggested_action: Suggested action type
    
    Returns:
        str: Constructed prompt
    """
    # Product information
    product_info = f"商品名称：{product.name}\n"
    product_info += f"商品SKU：{product.sku}\n"
    if product.price:
        product_info += f"商品价格：{product.price}元\n"
    if product.tags:
        tags_str = ", ".join(product.tags) if isinstance(product.tags, list) else str(product.tags)
        product_info += f"商品标签：{tags_str}\n"
    if product.description:
        product_info += f"商品描述：{product.description[:100]}...\n"  # Truncate if too long
    
    # Behavior summary
    visit_count = summary.get("visit_count", 0)
    max_stay_seconds = summary.get("max_stay_seconds", 0)
    avg_stay_seconds = summary.get("avg_stay_seconds", 0.0)
    has_enter_buy_page = summary.get("has_enter_buy_page", False)
    has_favorite = summary.get("has_favorite", False)
    has_click_size_chart = summary.get("has_click_size_chart", False)
    
    behavior_info = f"用户行为摘要：\n"
    behavior_info += f"- 访问次数：{visit_count}次\n"
    behavior_info += f"- 最大停留时间：{max_stay_seconds}秒\n"
    behavior_info += f"- 平均停留时间：{avg_stay_seconds:.1f}秒\n"
    behavior_info += f"- 是否进入购买页：{'是' if has_enter_buy_page else '否'}\n"
    behavior_info += f"- 是否收藏：{'是' if has_favorite else '否'}\n"
    behavior_info += f"- 是否查看尺码表：{'是' if has_click_size_chart else '否'}\n"
    
    # Action mapping to Chinese description
    action_descriptions = {
        ACTION_ASK_SIZE: "询问是否需要尺码推荐",
        ACTION_SEND_COUPON: "发送限时优惠券",
        ACTION_EXPLAIN_BENEFITS: "解释产品优势并温和推动",
        ACTION_PASSIVE_MESSAGE: "发送被动友好消息（不打扰）",
        ACTION_DO_NOT_DISTURB: "不打扰用户",
    }
    action_desc = action_descriptions.get(suggested_action, suggested_action)
    
    # Intent level mapping to Chinese
    intent_descriptions = {
        INTENT_HIGH: "高意图（强烈购买意向）",
        INTENT_MEDIUM: "中等意图（有一定兴趣）",
        INTENT_LOW: "低意图（购买意向较低）",
        INTENT_HESITATING: "犹豫（多次访问但未采取行动）",
    }
    intent_desc = intent_descriptions.get(intention_level, intention_level)
    
    # Construct full prompt
    prompt = f"""请根据以下信息，生成一条个性化的跟进消息：

## 商品信息：
{product_info}

## 用户行为摘要：
{behavior_info}

## 购买意图级别：
{intent_desc}

## 建议动作：
{action_desc}

## 要求：
1. 消息长度控制在50字以内
2. 根据意图级别调整语气和内容
3. 针对建议动作生成相应的消息
4. 语言自然友好，不要过于推销
5. 提供实际价值（如尺码建议、优惠信息、产品优势等）

请直接输出消息内容，不要包含其他说明："""
    
    return prompt


def _generate_rule_based_message(
    product: Product,
    summary: dict,
    intention_level: str,
    suggested_action: str,
) -> str:
    """
    Generate rule-based fallback message when LLM fails.
    
    Args:
        product: Product instance
        summary: Behavior summary dictionary
        intention_level: Intent level string
        suggested_action: Suggested action type
    
    Returns:
        str: Rule-based message
    """
    product_name = product.name
    tags = product.tags
    tag_str = ""
    if tags and isinstance(tags, list) and len(tags) > 0:
        tag_str = f"（{', '.join(tags[:2])}）"  # Use top 2 tags
    
    if suggested_action == ACTION_ASK_SIZE:
        return f"您好！看到您对这款{product_name}{tag_str}很感兴趣，需要我帮您推荐合适的尺码吗？"
    
    elif suggested_action == ACTION_SEND_COUPON:
        return f"您好！为您准备了限时优惠券，购买{product_name}{tag_str}可享受特别优惠，数量有限，先到先得！"
    
    elif suggested_action == ACTION_EXPLAIN_BENEFITS:
        # Extract key benefits from tags
        benefits = []
        if tags:
            if isinstance(tags, list):
                if "舒适" in tags:
                    benefits.append("舒适")
                if "时尚" in tags:
                    benefits.append("时尚")
                if "轻便" in tags:
                    benefits.append("轻便")
        benefit_str = "、".join(benefits[:2]) if benefits else "优质"
        
        return f"您好！{product_name}{tag_str}具有{benefit_str}等特点，非常适合您。如有任何疑问，欢迎随时咨询！"
    
    elif suggested_action == ACTION_PASSIVE_MESSAGE:
        return f"您好！{product_name}{tag_str}正在热销中，如有需要欢迎随时联系我们。"
    
    elif suggested_action == ACTION_DO_NOT_DISTURB:
        # For do_not_disturb, we still return a message but it's very passive
        return f"您好！{product_name}{tag_str}已为您保留，如有需要欢迎随时联系我们。"
    
    else:
        # Default fallback
        return f"您好！关于{product_name}{tag_str}，如有任何问题欢迎随时咨询。"


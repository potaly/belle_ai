"""Copy tool for generating private-chat sales copy (V5.3.0+).

重构说明：
- 从"营销广告"升级为"导购 1v1 私聊促单话术"
- 使用新的 prompt_templates 和 fallback_copy
- 根据 intent_level 使用不同策略
"""
from __future__ import annotations

import logging
from typing import Any

from app.agents.context import AgentContext
from app.core.config import get_settings
from app.services.fallback_copy import generate_fallback_copy
from app.services.llm_client import LLMClientError, get_llm_client
from app.services.prompt_templates import (
    build_system_prompt,
    build_user_prompt,
    validate_copy_output,
)

logger = logging.getLogger(__name__)


async def generate_marketing_copy(
    context: AgentContext,
    style: Any = None,  # Legacy parameter, ignored in V5.3.0+
    **kwargs: Any,
) -> AgentContext:
    """
    生成导购 1v1 私聊促单话术并添加到上下文消息。
    
    调用逻辑：
    - 通常在 classify_intent 和 anti_disturb_check 之后执行
    - 前提条件：context.product 和 context.intent_level 必须已设置
    - 根据 intent_level 使用不同策略
    - LLM 失败时自动降级到规则模板
    
    Args:
        context: Agent context (must have product and intent_level set)
        style: Legacy parameter (ignored in V5.3.0+)
        **kwargs: Additional arguments (ignored)
    
    Returns:
        Updated AgentContext with generated copy added to messages
    """
    logger.info("=" * 80)
    logger.info("[COPY_TOOL] Generating private-chat sales copy")
    logger.info(
        f"[COPY_TOOL] Context: sku={context.sku}, "
        f"intent_level={context.intent_level}, "
        f"has_product={context.product is not None}"
    )
    
    # Validate prerequisites
    if not context.product:
        error_msg = "Product is required in context to generate copy"
        logger.error(f"[COPY_TOOL] ✗ {error_msg}")
        context.add_message("assistant", "抱歉，无法生成话术：缺少商品信息。")
        return context
    
    if not context.intent_level:
        error_msg = "Intent level is required in context to generate copy"
        logger.error(f"[COPY_TOOL] ✗ {error_msg}")
        context.add_message("assistant", "抱歉，无法生成话术：缺少意图分析结果。")
        return context
    
    # Get configuration
    settings = get_settings()
    max_length = settings.copy_max_length
    
    # Get intent reason from context
    intent_reason = context.extra.get("intent_reason", "用户浏览了商品")
    behavior_summary = context.behavior_summary
    
    try:
        # Build prompts
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(
            product=context.product,
            intent_level=context.intent_level,
            intent_reason=intent_reason,
            behavior_summary=behavior_summary,
            max_length=max_length,
        )
        
        logger.info(f"[COPY_TOOL] Prompt built: {len(user_prompt)} chars")
        logger.debug(f"[COPY_TOOL] === [DEBUG] System Prompt ===\n{system_prompt}\n=== [END] ===")
        logger.debug(f"[COPY_TOOL] === [DEBUG] User Prompt ===\n{user_prompt[:500]}...\n=== [END] ===")
        
        # Try LLM generation
        llm_used = False
        copy_text = None
        
        llm_client = get_llm_client()
        if llm_client.settings.llm_api_key and llm_client.settings.llm_base_url:
            logger.info("[COPY_TOOL] Calling LLM to generate copy...")
            
            try:
                full_response = ""
                async for chunk in llm_client.stream_chat(
                    user_prompt,
                    system=system_prompt,
                    temperature=0.7,  # Lower temperature for more controlled output
                    max_tokens=150,
                ):
                    if chunk:
                        full_response += chunk
                
                copy_text = full_response.strip()
                
                # Validate output
                is_valid, error_msg = validate_copy_output(copy_text, max_length)
                if is_valid:
                    llm_used = True
                    logger.info(
                        f"[COPY_TOOL] ✓ LLM generation successful: "
                        f"{len(copy_text)} chars"
                    )
                else:
                    logger.warning(
                        f"[COPY_TOOL] ⚠ LLM output validation failed: {error_msg}, "
                        f"falling back to template"
                    )
                    copy_text = None
                    
            except LLMClientError as e:
                logger.warning(f"[COPY_TOOL] ⚠ LLM error: {e}, falling back to template")
            except Exception as e:
                logger.error(
                    f"[COPY_TOOL] ✗ Unexpected error during LLM generation: {e}",
                    exc_info=True,
                )
        else:
            logger.warning(f"[COPY_TOOL] LLM not configured, using fallback")
        
        # Fallback to rule-based template
        if not copy_text or not llm_used:
            logger.info(f"[COPY_TOOL] Using fallback template...")
            copy_text = generate_fallback_copy(
                product=context.product,
                intent_level=context.intent_level,
                max_length=max_length,
            )
            llm_used = False
            logger.info(
                f"[COPY_TOOL] ✓ Fallback copy generated: {len(copy_text)} chars"
            )
        
        # Store diagnostics in context
        context.extra["copy_llm_used"] = llm_used
        context.extra["copy_strategy"] = _get_strategy_description(context.intent_level)
        
        # Add to context messages
        context.add_message("assistant", copy_text)
        
        logger.info(
            f"[COPY_TOOL] ✓ Copy generated: {len(copy_text)} chars, "
            f"llm_used={llm_used}, strategy={context.extra['copy_strategy']}"
        )
        logger.info(f"[COPY_TOOL] Generated copy: {copy_text}")
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(
            f"[COPY_TOOL] ✗ Error generating copy: {e}",
            exc_info=True,
        )
        # Fallback to simple template
        try:
            copy_text = generate_fallback_copy(
                product=context.product,
                intent_level=context.intent_level,
                max_length=max_length,
            )
            context.add_message("assistant", copy_text)
            logger.info(f"[COPY_TOOL] ✓ Emergency fallback copy generated")
        except Exception as fallback_error:
            logger.error(f"[COPY_TOOL] ✗ Fallback also failed: {fallback_error}")
            context.add_message("assistant", "抱歉，话术生成失败，请稍后重试。")
        
        return context


def _get_strategy_description(intent_level: str) -> str:
    """Get strategy description for logging."""
    strategies = {
        "high": "主动推进（询问尺码/提醒库存）",
        "hesitating": "消除顾虑（轻量提问）",
        "medium": "场景化推荐",
        "low": "轻量提醒（不施压）",
    }
    return strategies.get(intent_level, "场景化推荐")

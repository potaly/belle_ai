"""Sales agent for anti-disturb mechanism and sales logic."""
from __future__ import annotations

import logging
from typing import Optional

from app.agents.context import AgentContext
from app.services.intent_engine import (
    INTENT_HIGH,
    INTENT_HESITATING,
    INTENT_LOW,
    INTENT_MEDIUM,
)

logger = logging.getLogger(__name__)


def allow_touch(
    context: AgentContext,
    intent_level: Optional[str] = None,
) -> bool:
    """
    判断是否允许主动接触用户（反打扰机制）。
    
    核心规则：
    - 低意图用户：默认不允许主动接触（除非强制标记）
    - 高/中意图用户：允许主动接触
    - 犹豫用户：允许温和接触
    - 可通过 context.extra["force_allow"] 强制允许
    
    Args:
        context: Agent context
        intent_level: Intent level (if not provided, uses context.intent_level)
    
    Returns:
        True if contact is allowed, False otherwise
    """
    # 强制允许标记（用于特殊场景）
    if context.extra.get("force_allow", False):
        logger.debug("[SALES_AGENT] Force allow enabled")
        return True
    
    # 获取意图级别
    level = intent_level or context.intent_level
    
    if not level:
        # 如果没有意图级别，默认不允许（保守策略）
        logger.debug("[SALES_AGENT] No intent level, defaulting to not allowed")
        return False
    
    # 根据意图级别决定
    if level == INTENT_LOW:
        # 低意图：不允许主动接触
        logger.debug("[SALES_AGENT] Low intent, contact not allowed")
        return False
    elif level in (INTENT_HIGH, INTENT_MEDIUM):
        # 高/中意图：允许主动接触
        logger.debug(f"[SALES_AGENT] {level} intent, contact allowed")
        return True
    elif level == INTENT_HESITATING:
        # 犹豫用户：允许温和接触
        logger.debug("[SALES_AGENT] Hesitating intent, gentle contact allowed")
        return True
    else:
        # 未知意图级别：默认不允许
        logger.warning(f"[SALES_AGENT] Unknown intent level: {level}, defaulting to not allowed")
        return False


async def anti_disturb_check_node(context: AgentContext) -> AgentContext:
    """
    反打扰检查节点：判断是否允许主动接触用户。
    
    调用逻辑：
    - 通常在 classify_intent 之后执行（anti_disturb_check）
    - 前提条件：context.intent_level 应该已设置（通过 classify_intent_node）
    - 调用场景：规划器在意图分类后自动添加此检查
    - 调用后：context.extra["allowed"] 被设置（True/False），影响后续内容生成决策
    - 依赖关系：此节点的输出决定是否执行 generate_copy 或 generate_followup
    
    Args:
        context: Agent context (should have intent_level set)
    
    Returns:
        Updated AgentContext with anti-disturb check result in extra["allowed"]
    """
    logger.info("=" * 80)
    logger.info("[SALES_AGENT] Performing anti-disturb check")
    logger.info(
        f"[SALES_AGENT] Context: user_id={context.user_id}, sku={context.sku}, "
        f"intent_level={context.intent_level}"
    )
    
    try:
        # 核心逻辑：调用反打扰判断函数，基于意图级别决定是否允许接触
        allowed = allow_touch(context, context.intent_level)
        
        # 更新上下文：保存检查结果
        context.extra["allowed"] = allowed
        context.extra["anti_disturb_blocked"] = not allowed
        
        if allowed:
            logger.info(
                f"[SALES_AGENT] ✓ Contact allowed for intent_level={context.intent_level}"
            )
        else:
            logger.info(
                f"[SALES_AGENT] ✗ Contact blocked (anti-disturb) for intent_level={context.intent_level}"
            )
        
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(
            f"[SALES_AGENT] ✗ Error in anti-disturb check: {e}",
            exc_info=True,
        )
        # 错误时默认不允许（保守策略）
        context.extra["allowed"] = False
        context.extra["anti_disturb_blocked"] = True
        return context


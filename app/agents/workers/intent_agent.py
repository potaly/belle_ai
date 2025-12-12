"""Intent agent for classifying user purchase intent."""
from __future__ import annotations

import logging

from app.agents.context import AgentContext
from app.services.intent_engine import classify_intent

logger = logging.getLogger(__name__)


async def classify_intent_node(context: AgentContext) -> AgentContext:
    """
    意图分类节点：分析用户购买意图并保存到上下文。
    
    调用逻辑：
    - 通常在 fetch_behavior_summary 之后执行（classify_intent）
    - 前提条件：context.behavior_summary 必须已设置
    - 调用场景：规划器检测到有行为摘要但意图未分类时自动添加
    - 调用后：context.intent_level 被填充（high/medium/low/hesitating），供后续节点使用
    - 依赖关系：此节点的输出影响 RAG 检索和内容生成的决策
    
    Args:
        context: Agent context (must have behavior_summary set)
    
    Returns:
        Updated AgentContext with intent_level populated
    
    Raises:
        ValueError: If behavior_summary is missing
    """
    logger.info("=" * 80)
    logger.info("[INTENT_AGENT] Classifying user intent")
    logger.info(
        f"[INTENT_AGENT] Context: user_id={context.user_id}, sku={context.sku}, "
        f"has_behavior_summary={context.behavior_summary is not None}"
    )
    
    if not context.behavior_summary:
        error_msg = "behavior_summary is required in context to classify intent"
        logger.error(f"[INTENT_AGENT] ✗ {error_msg}")
        raise ValueError(error_msg)
    
    try:
        # 核心逻辑：调用意图分析引擎，基于行为摘要分类意图
        result = classify_intent(context.behavior_summary)
        
        # 更新上下文：保存意图级别和原因（确保永远不为 None）
        context.intent_level = result.level
        context.extra["intent_reason"] = result.reason
        
        logger.info(
            f"[INTENT_AGENT] ✓ Intent classified: level={result.level}, "
            f"reason={result.reason[:50]}..."
        )
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(
            f"[INTENT_AGENT] ✗ Error classifying intent: {e}",
            exc_info=True,
        )
        # 错误时设置为低意图，避免后续节点误判
        context.intent_level = "low"
        context.extra["intent_reason"] = "意图分类失败，默认设为低意图"
        return context


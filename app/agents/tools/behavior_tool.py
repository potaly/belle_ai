"""Behavior tool for fetching and summarizing user behavior."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.repositories.behavior_repository import get_recent_behavior

logger = logging.getLogger(__name__)


def summarize_behavior(logs: list) -> dict:
    """
    将用户行为日志汇总为摘要字典。
    
    核心逻辑：计算访问次数、停留时间统计、关键行为标志（进入购买页、收藏等）
    
    Args:
        logs: List of UserBehaviorLog instances
    
    Returns:
        Dictionary with summarized behavior metrics
    """
    if not logs:
        return {
            "visit_count": 0,
            "max_stay_seconds": 0,
            "avg_stay_seconds": 0.0,
            "total_stay_seconds": 0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "has_share": False,
            "has_click_size_chart": False,
            "event_types": [],
        }
    
    # Calculate statistics
    stay_seconds_list = [log.stay_seconds for log in logs]
    max_stay_seconds = max(stay_seconds_list) if stay_seconds_list else 0
    total_stay_seconds = sum(stay_seconds_list)
    avg_stay_seconds = total_stay_seconds / len(logs) if logs else 0.0
    
    # Check for specific events
    event_types = [log.event_type for log in logs]
    event_type_counts = {}
    for event_type in event_types:
        event_type_counts[event_type] = event_type_counts.get(event_type, 0) + 1
    
    has_enter_buy_page = "enter_buy_page" in event_types
    has_favorite = "favorite" in event_types
    has_share = "share" in event_types
    has_click_size_chart = "click_size_chart" in event_types
    
    summary = {
        "visit_count": len(logs),
        "max_stay_seconds": max_stay_seconds,
        "avg_stay_seconds": round(avg_stay_seconds, 2),
        "total_stay_seconds": total_stay_seconds,
        "has_enter_buy_page": has_enter_buy_page,
        "has_favorite": has_favorite,
        "has_share": has_share,
        "has_click_size_chart": has_click_size_chart,
        "event_types": list(set(event_types)),
        "event_type_counts": event_type_counts,
    }
    
    return summary


async def fetch_behavior_summary(
    context: AgentContext,
    db: Session,
    limit: int = 50,
    **kwargs: Any,
) -> AgentContext:
    """
    获取用户行为摘要并添加到上下文。
    
    调用逻辑：
    - 通常在 fetch_product 之后执行（fetch_behavior_summary）
    - 前提条件：context.user_id 和 context.sku 必须已设置
    - 调用场景：需要分析用户意图时，规划器会自动添加此任务
    - 调用后：context.behavior_summary 被填充，供 classify_intent 使用
    - 依赖关系：此工具的输出是意图分类的输入
    
    This tool reads user behavior logs from the database, summarizes them
    using summarize_behavior(), and saves the summary to context.behavior_summary.
    
    Args:
        context: Agent context (must have user_id and sku set)
        db: Database session
        limit: Maximum number of behavior logs to retrieve (default: 50)
        **kwargs: Additional arguments (ignored)
    
    Returns:
        Updated AgentContext with behavior_summary populated
    
    Example:
        >>> context = AgentContext(user_id="user_001", sku="8WZ01CM1")
        >>> context = await fetch_behavior_summary(context, db, limit=50)
        >>> print(context.behavior_summary["visit_count"])
        2
    """
    logger.info("=" * 80)
    logger.info("[BEHAVIOR_TOOL] Fetching behavior summary")
    logger.info(
        f"[BEHAVIOR_TOOL] Context: user_id={context.user_id}, "
        f"sku={context.sku}, limit={limit}"
    )
    
    if not context.user_id or not context.sku:
        logger.warning(
            "[BEHAVIOR_TOOL] Missing user_id or sku in context, "
            "returning empty summary"
        )
        context.behavior_summary = summarize_behavior([])
        return context
    
    try:
        # Fetch behavior logs
        logs = await get_recent_behavior(
            db=db,
            user_id=context.user_id,
            sku=context.sku,
            limit=limit,
        )
        
        # Summarize behavior
        summary = summarize_behavior(logs)
        
        # Update context
        context.behavior_summary = summary
        
        logger.info(
            f"[BEHAVIOR_TOOL] ✓ Behavior summary created: "
            f"visit_count={summary['visit_count']}, "
            f"max_stay={summary['max_stay_seconds']}s, "
            f"enter_buy_page={summary['has_enter_buy_page']}"
        )
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(
            f"[BEHAVIOR_TOOL] ✗ Error fetching behavior summary: {e}",
            exc_info=True,
        )
        # Return empty summary on error
        context.behavior_summary = summarize_behavior([])
        return context


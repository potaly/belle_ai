"""User behavior repository for database access."""
from __future__ import annotations

import logging
from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.user_behavior_log import UserBehaviorLog

logger = logging.getLogger(__name__)


async def get_recent_behavior(
    db: Session,
    user_id: str,
    sku: str,
    limit: int = 50,
) -> List[UserBehaviorLog]:
    """
    Get recent behavior logs for a specific user and product.
    
    Args:
        db: Database session
        user_id: User ID to filter by
        sku: Product SKU to filter by
        limit: Maximum number of logs to return (default: 50)
        
    Returns:
        List of UserBehaviorLog instances, ordered by occurred_at DESC (newest first)
        Returns empty list if no logs found or on error
        
    Raises:
        Exception: Re-raises any database exceptions for caller to handle
    """
    logger.info(
        f"[BEHAVIOR_REPOSITORY] Querying recent behavior: user_id={user_id}, "
        f"sku={sku}, limit={limit}"
    )
    
    try:
        # Query user_behavior_logs table
        # Filter by user_id and sku
        # Sort by occurred_at DESC (newest first)
        # Limit to latest `limit` logs
        logs = (
            db.query(UserBehaviorLog)
            .filter(
                UserBehaviorLog.user_id == user_id,
                UserBehaviorLog.sku == sku,
            )
            .order_by(desc(UserBehaviorLog.occurred_at))
            .limit(limit)
            .all()
        )
        
        if logs:
            logger.info(
                f"[BEHAVIOR_REPOSITORY] ✓ Found {len(logs)} behavior logs "
                f"(user_id={user_id}, sku={sku})"
            )
            
            # Log summary of event types
            event_counts = {}
            for log in logs:
                event_type = log.event_type
                event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            logger.debug(
                f"[BEHAVIOR_REPOSITORY] Event type distribution: {event_counts}"
            )
            
            # Log time range
            if len(logs) > 0:
                oldest = logs[-1].occurred_at
                newest = logs[0].occurred_at
                logger.debug(
                    f"[BEHAVIOR_REPOSITORY] Time range: {oldest} to {newest}"
                )
        else:
            logger.info(
                f"[BEHAVIOR_REPOSITORY] No behavior logs found "
                f"(user_id={user_id}, sku={sku})"
            )
        
        return logs
        
    except Exception as e:
        logger.error(
            f"[BEHAVIOR_REPOSITORY] ✗ Error querying behavior logs: {e}",
            exc_info=True,
        )
        # Re-raise exception for caller to handle
        raise


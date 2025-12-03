"""Intent analysis API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.behavior_repository import get_recent_behavior
from app.schemas.intent_schemas import (
    BehaviorSummary,
    IntentAnalysisRequest,
    IntentAnalysisResponse,
)
from app.services.intent_engine import classify_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai", "intent"])


@router.post("/analyze/intent", response_model=IntentAnalysisResponse)
async def analyze_intent(
    request: IntentAnalysisRequest,
    db: Session = Depends(get_db),
) -> IntentAnalysisResponse:
    """
    Analyze user purchase intent based on behavior logs.
    
    This endpoint retrieves user behavior logs for a specific product and
    uses the intent analysis engine to classify the user's purchase intention.
    
    **V3 Feature**: User behavior analysis and intent classification.
    
    Args:
        request: Intent analysis request containing user_id, sku, and limit
        db: Database session
        
    Returns:
        IntentAnalysisResponse with intent level, reason, and behavior summary
        
    Raises:
        HTTPException:
            - 404 if user_id or sku not found (no behavior logs)
            - 500 if analysis fails
            
    Example Request:
        ```json
        {
            "user_id": "user_001",
            "sku": "8WZ01CM1",
            "limit": 50
        }
        ```
        
    Example Response:
        ```json
        {
            "user_id": "user_001",
            "sku": "8WZ01CM1",
            "intent_level": "high",
            "reason": "用户已进入购买页面，这是强烈的购买信号。访问次数：2次，最大停留：25秒",
            "behavior_summary": {
                "visit_count": 2,
                "max_stay_seconds": 25,
                "avg_stay_seconds": 20.0,
                "has_enter_buy_page": true,
                "has_favorite": false,
                ...
            },
            "total_logs_analyzed": 2
        }
        ```
    """
    logger.info("=" * 80)
    logger.info("[API] POST /ai/analyze/intent - Request received")
    logger.info(
        f"[API] Request parameters: user_id={request.user_id}, "
        f"sku={request.sku}, limit={request.limit}"
    )
    
    try:
        # Step 1: Retrieve behavior logs
        logger.info("[API] Step 1: Retrieving behavior logs...")
        logs = await get_recent_behavior(
            db=db,
            user_id=request.user_id,
            sku=request.sku,
            limit=request.limit,
        )
        
        if not logs:
            logger.warning(
                f"[API] No behavior logs found for user_id={request.user_id}, sku={request.sku}"
            )
            # Return low intent with empty summary
            return IntentAnalysisResponse(
                user_id=request.user_id,
                sku=request.sku,
                intent_level="low",
                reason="无行为记录，无法分析购买意图",
                behavior_summary=None,
                total_logs_analyzed=0,
            )
        
        logger.info(f"[API] ✓ Retrieved {len(logs)} behavior logs")
        
        # Step 2: Build behavior summary
        logger.info("[API] Step 2: Building behavior summary...")
        
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
        
        summary_dict = {
            "visit_count": len(logs),
            "max_stay_seconds": max_stay_seconds,
            "avg_stay_seconds": round(avg_stay_seconds, 2),
            "total_stay_seconds": total_stay_seconds,
            "has_enter_buy_page": has_enter_buy_page,
            "has_favorite": has_favorite,
            "has_share": has_share,
            "has_click_size_chart": has_click_size_chart,
            "event_types": list(set(event_types)),
        }
        
        logger.info(
            f"[API] ✓ Summary built: visits={summary_dict['visit_count']}, "
            f"max_stay={max_stay_seconds}s, avg_stay={avg_stay_seconds:.1f}s, "
            f"enter_buy_page={has_enter_buy_page}, favorite={has_favorite}"
        )
        
        # Step 3: Classify intent
        logger.info("[API] Step 3: Classifying intent...")
        intent_level, reason = classify_intent(summary_dict)
        
        logger.info(f"[API] ✓ Intent classified: {intent_level}")
        logger.info(f"[API] Reason: {reason}")
        
        # Step 4: Build response
        behavior_summary = BehaviorSummary(
            visit_count=summary_dict["visit_count"],
            max_stay_seconds=summary_dict["max_stay_seconds"],
            avg_stay_seconds=summary_dict["avg_stay_seconds"],
            total_stay_seconds=summary_dict["total_stay_seconds"],
            has_enter_buy_page=summary_dict["has_enter_buy_page"],
            has_favorite=summary_dict["has_favorite"],
            has_share=summary_dict["has_share"],
            has_click_size_chart=summary_dict["has_click_size_chart"],
            event_types=summary_dict["event_types"],
            event_type_counts=event_type_counts,
        )
        
        response = IntentAnalysisResponse(
            user_id=request.user_id,
            sku=request.sku,
            intent_level=intent_level,
            reason=reason,
            behavior_summary=behavior_summary,
            total_logs_analyzed=len(logs),
        )
        
        logger.info("[API] ✓ Response built successfully")
        logger.info("=" * 80)
        
        return response
        
    except HTTPException:
        # Re-raise HTTP exceptions
        logger.info("=" * 80)
        raise
    except Exception as e:
        logger.error(
            f"[API] ✗ Unexpected error in analyze_intent endpoint: {e}",
            exc_info=True,
        )
        logger.info("=" * 80)
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze intent: {str(e)}"
        )


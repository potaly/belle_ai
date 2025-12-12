"""Follow-up suggestion API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.behavior_repository import get_recent_behavior
from app.repositories.product_repository import get_product_by_sku
from app.schemas.followup_schemas import FollowupRequest, FollowupResponse, FollowupResponseData
from app.services.followup_service import generate_followup_suggestion
from app.services.intent_engine import classify_intent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai", "followup"])


@router.post("/followup/suggest", response_model=FollowupResponse)
async def suggest_followup(
    request: FollowupRequest,
    db: Session = Depends(get_db),
) -> FollowupResponse:
    """
    生成个性化跟进建议。
    
    本接口分析用户行为日志，分类购买意图，并生成个性化的跟进消息和建议动作。
    
    **V3 功能特性**：智能跟进建议，包含反打扰机制。
    
    参数说明:
        request: 跟进建议请求，包含 user_id、sku 和 limit
        db: 数据库会话
        
    返回值:
        FollowupResponse，包含建议动作和个性化消息
        
    异常:
        HTTPException:
            - 404: 如果商品未找到
            - 500: 如果分析失败
            
    请求示例:
        ```json
        {
            "user_id": "user_001",
            "sku": "8WZ01CM1",
            "limit": 50
        }
        ```
        
    响应示例:
        ```json
        {
            "success": true,
            "message": "跟进建议生成成功",
            "data": {
                "user_id": "user_001",
                "sku": "8WZ01CM1",
                "product_name": "舒适跑鞋",
                "intention_level": "high",
                "suggested_action": "ask_size",
                "message": "您好！看到您对这款舒适跑鞋很感兴趣，需要我帮您推荐合适的尺码吗？",
                "behavior_summary": {
                    "visit_count": 2,
                    "max_stay_seconds": 30,
                    "avg_stay_seconds": 20.0,
                    "has_enter_buy_page": true
                },
                "total_logs_analyzed": 2
            }
        }
        ```
    """
    logger.info("=" * 80)
    logger.info("[API] POST /ai/followup/suggest - Request received")
    logger.info(
        f"[API] Request parameters: user_id={request.user_id}, "
        f"sku={request.sku}, limit={request.limit}"
    )
    
    try:
        # Step 1: Validate product exists
        logger.info("[API] Step 1: Validating product exists...")
        product = get_product_by_sku(db, request.sku)
        if not product:
            logger.warning(f"[API] Product not found: sku={request.sku}")
            raise HTTPException(
                status_code=404, detail=f"Product with SKU {request.sku} not found"
            )
        logger.info(f"[API] ✓ Product found: name={product.name}, sku={product.sku}")
        
        # Step 2: Retrieve behavior logs
        logger.info("[API] Step 2: Retrieving behavior logs...")
        logs = await get_recent_behavior(
            db=db,
            user_id=request.user_id,
            sku=request.sku,
            limit=request.limit,
        )
        
        # Step 3: Build behavior summary
        logger.info("[API] Step 3: Building behavior summary...")
        
        if not logs:
            logger.info(f"[API] No behavior logs found, using default low intent")
            summary = {
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
            intention_level = "low"
        else:
            logger.info(f"[API] ✓ Retrieved {len(logs)} behavior logs")
            
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
            }
            
            # Step 4: Classify intent
            logger.info("[API] Step 4: Classifying intent...")
            result = classify_intent(summary)
            intention_level = result.level
            reason = result.reason
            logger.info(f"[API] ✓ Intent classified: {intention_level}, reason: {reason}")
        
        # Step 5: Generate follow-up suggestion
        logger.info("[API] Step 5: Generating follow-up suggestion...")
        followup_result = await generate_followup_suggestion(
            product=product,
            summary=summary,
            intention_level=intention_level,
        )
        
        logger.info(
            f"[API] ✓ Follow-up suggestion generated: "
            f"action={followup_result['suggested_action']}, "
            f"message_length={len(followup_result['message'])}"
        )
        
        # Step 6: Build response
        response_data = FollowupResponseData(
            user_id=request.user_id,
            sku=request.sku,
            product_name=product.name,
            intention_level=intention_level,
            suggested_action=followup_result["suggested_action"],
            message=followup_result["message"],
            behavior_summary=summary if logs else None,
            total_logs_analyzed=len(logs),
        )
        
        logger.info("[API] ✓ Response built successfully")
        logger.info("=" * 80)
        
        return FollowupResponse(
            success=True,
            message="跟进建议生成成功",
            data=response_data,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        logger.info("=" * 80)
        raise
    except Exception as e:
        logger.error(
            f"[API] ✗ Unexpected error in suggest_followup endpoint: {e}",
            exc_info=True,
        )
        logger.info("=" * 80)
        raise HTTPException(
            status_code=500, detail=f"Failed to generate follow-up suggestion: {str(e)}"
        )


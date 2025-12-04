"""Sales graph API endpoints."""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.graph.sales_graph import run_sales_graph
from app.agents.planner_agent import plan_sales_flow
from app.core.database import get_db
from app.schemas.sales_graph_schemas import SalesGraphRequest, SalesGraphResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/sales/graph", response_model=SalesGraphResponse)
async def execute_sales_graph(
    request: SalesGraphRequest,
    db: Session = Depends(get_db),
) -> SalesGraphResponse:
    """
    执行销售流程图。
    
    这个接口使用 LangGraph 状态机来编排整个销售流程，包括：
    - 获取商品信息
    - 获取用户行为摘要
    - 分类用户意图
    - 反打扰检查
    - 检索 RAG 上下文（可选）
    - 生成营销文案
    
    流程会根据用户意图和反打扰规则自动决定执行路径。
    
    Args:
        request: 销售图执行请求
        db: 数据库会话
        
    Returns:
        SalesGraphResponse: 执行结果，包含意图级别、生成的文案等信息
        
    Example:
        ```json
        {
            "user_id": "user_001",
            "sku": "8WZ01CM1",
            "guide_id": "guide_001",
            "use_custom_plan": false
        }
        ```
    """
    logger.info("=" * 80)
    logger.info("[API] POST /ai/sales/graph - Request received")
    logger.info(
        f"[API] Request: user_id={request.user_id}, sku={request.sku}, "
        f"guide_id={request.guide_id}, use_custom_plan={request.use_custom_plan}"
    )
    
    start_time = time.time()
    
    try:
        # 创建初始上下文
        context = AgentContext(
            user_id=request.user_id,
            guide_id=request.guide_id,
            sku=request.sku,
        )
        
        # 决定执行计划
        plan: list[str] | None = None
        if request.use_custom_plan:
            logger.info("[API] Generating custom plan using planner")
            plan = await plan_sales_flow(context)
            logger.info(f"[API] Generated plan: {plan}")
        
        # 执行销售图
        logger.info("[API] Executing sales graph...")
        result_context = await run_sales_graph(context, plan=plan)
        
        execution_time = time.time() - start_time
        
        # 构建响应数据
        response_data: dict[str, Any] = {
            "user_id": result_context.user_id,
            "sku": result_context.sku,
            "intent_level": result_context.intent_level,
            "allowed": result_context.extra.get("allowed", False),
            "anti_disturb_blocked": result_context.extra.get("anti_disturb_blocked", False),
            "messages_count": len(result_context.messages),
            "rag_chunks_count": len(result_context.rag_chunks),
            "execution_time_seconds": round(execution_time, 3),
        }
        
        # 添加计划信息
        if plan:
            response_data["plan_used"] = plan
        else:
            response_data["plan_used"] = "full_graph_flow"
        
        # 添加意图原因
        if "intent_reason" in result_context.extra:
            response_data["intent_reason"] = result_context.extra["intent_reason"]
        
        # 添加最后一条消息（通常是生成的文案）
        if result_context.messages:
            last_message = result_context.messages[-1]
            if last_message.get("role") == "assistant":
                response_data["final_message"] = last_message.get("content", "")
        
        # 添加商品信息摘要（如果有）
        if result_context.product:
            response_data["product_name"] = result_context.product.name
            response_data["product_price"] = float(result_context.product.price)
        
        logger.info(
            f"[API] ✓ Sales graph executed successfully in {execution_time:.3f}s. "
            f"Intent: {result_context.intent_level}, "
            f"Allowed: {result_context.extra.get('allowed')}, "
            f"Messages: {len(result_context.messages)}"
        )
        logger.info("=" * 80)
        
        return SalesGraphResponse(
            success=True,
            message="Sales graph executed successfully",
            data=response_data,
        )
        
    except Exception as e:
        execution_time = time.time() - start_time
        
        logger.error(
            f"[API] ✗ Sales graph execution failed after {execution_time:.3f}s: {e}",
            exc_info=True,
        )
        logger.info("=" * 80)
        
        raise HTTPException(
            status_code=500,
            detail=f"Sales graph execution failed: {str(e)}",
        )


@router.get("/sales/graph/health")
async def sales_graph_health() -> dict[str, str]:
    """
    检查销售图服务的健康状态。
    
    Returns:
        Health status information
    """
    try:
        from app.agents.graph.sales_graph import get_sales_graph
        
        graph = get_sales_graph()
        
        return {
            "status": "ok",
            "graph_compiled": "true" if graph is not None else "false",
            "message": "Sales graph service is healthy",
        }
    except Exception as e:
        logger.error(f"[API] Sales graph health check failed: {e}", exc_info=True)
        return {
            "status": "error",
            "graph_compiled": "false",
            "message": f"Health check failed: {str(e)}",
        }


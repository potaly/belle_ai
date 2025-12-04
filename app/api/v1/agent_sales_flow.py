"""Agent-based sales flow API endpoint."""
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
from app.schemas.agent_sales_flow_schemas import (
    AgentSalesFlowRequest,
    AgentSalesFlowResponse,
    MessageItem,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai", "agent"])


@router.post("/agent/sales_flow", response_model=AgentSalesFlowResponse)
async def execute_agent_sales_flow(
    request: AgentSalesFlowRequest,
    db: Session = Depends(get_db),
) -> AgentSalesFlowResponse:
    """
    执行 AI 智能销售 Agent 完整流程。
    
    这是 V4 版本的最终产物，整合了所有 Agent 功能：
    - AgentContext: 上下文管理
    - Planner: 智能任务规划
    - Tools: 工具调用（商品、行为、RAG、文案）
    - Workers: 工作节点（意图分类、反打扰检查、文案生成）
    - LangGraph: 状态机编排
    
    完整流程：
    1. 初始化 AgentContext
    2. 使用规划器生成执行计划
    3. 执行 LangGraph 销售流程图
    4. 返回最终结果摘要
    
    Args:
        request: Agent 销售流程请求
        db: 数据库会话
        
    Returns:
        AgentSalesFlowResponse: 包含商品信息、行为摘要、意图、消息等完整结果
        
    Raises:
        HTTPException: 如果执行失败
        
    Example Request:
        ```json
        {
            "user_id": "user_001",
            "guide_id": "guide_001",
            "sku": "8WZ01CM1"
        }
        ```
        
    Example Response:
        ```json
        {
            "success": true,
            "message": "Agent sales flow executed successfully",
            "data": {
                "user_id": "user_001",
                "sku": "8WZ01CM1",
                "product": {...},
                "behavior_summary": {...},
                "intent": {...},
                "allowed": true,
                "rag_used": true,
                "messages": [...]
            }
        }
        ```
    """
    logger.info("=" * 80)
    logger.info("[AGENT_API] POST /ai/agent/sales_flow - Request received")
    logger.info(
        f"[AGENT_API] Request: user_id={request.user_id}, "
        f"guide_id={request.guide_id}, sku={request.sku}"
    )
    
    start_time = time.time()
    
    try:
        # Step 1: Initialize AgentContext
        logger.info("[AGENT_API] Step 1: Initializing AgentContext...")
        context = AgentContext(
            user_id=request.user_id,
            guide_id=request.guide_id,
            sku=request.sku,
        )
        logger.info(
            f"[AGENT_API] ✓ Context initialized: user_id={context.user_id}, "
            f"sku={context.sku}, guide_id={context.guide_id}"
        )
        
        # Step 2: Generate execution plan using planner
        logger.info("[AGENT_API] Step 2: Generating execution plan...")
        plan = await plan_sales_flow(context)
        logger.info(f"[AGENT_API] ✓ Plan generated: {plan}")
        
        # Step 3: Execute sales graph with plan
        logger.info("[AGENT_API] Step 3: Executing sales graph...")
        result_context = await run_sales_graph(context, plan=plan)
        logger.info(
            f"[AGENT_API] ✓ Graph execution completed. "
            f"Intent: {result_context.intent_level}, "
            f"Messages: {len(result_context.messages)}"
        )
        
        execution_time = time.time() - start_time
        
        # Step 4: Build response data
        logger.info("[AGENT_API] Step 4: Building response data...")
        response_data: dict[str, Any] = {
            "user_id": result_context.user_id,
            "guide_id": result_context.guide_id,
            "sku": result_context.sku,
            "execution_time_seconds": round(execution_time, 3),
        }
        
        # Add product information
        if result_context.product:
            # Handle tags: could be string or list
            tags = result_context.product.tags
            if isinstance(tags, str):
                tags_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            elif isinstance(tags, list):
                tags_list = tags
            else:
                tags_list = []
            
            response_data["product"] = {
                "name": result_context.product.name,
                "price": float(result_context.product.price),
                "tags": tags_list,
                "sku": result_context.product.sku,
            }
        
        # Add behavior summary
        if result_context.behavior_summary:
            response_data["behavior_summary"] = result_context.behavior_summary
        
        # Add intent information
        if result_context.intent_level:
            response_data["intent"] = {
                "level": result_context.intent_level,
                "reason": result_context.extra.get("intent_reason", ""),
            }
        
        # Add anti-disturb check results
        response_data["allowed"] = result_context.extra.get("allowed", False)
        response_data["anti_disturb_blocked"] = result_context.extra.get(
            "anti_disturb_blocked", False
        )
        
        # Add RAG information
        rag_used = len(result_context.rag_chunks) > 0
        response_data["rag_used"] = rag_used
        response_data["rag_chunks_count"] = len(result_context.rag_chunks)
        
        # Add messages
        messages = [
            MessageItem(role=msg.get("role", "unknown"), content=msg.get("content", ""))
            for msg in result_context.messages
        ]
        response_data["messages"] = [msg.model_dump() for msg in messages]
        
        # Add execution plan
        response_data["plan_executed"] = plan
        
        logger.info(
            f"[AGENT_API] ✓ Response built successfully. "
            f"Product: {response_data.get('product', {}).get('name', 'N/A')}, "
            f"Intent: {response_data.get('intent', {}).get('level', 'N/A')}, "
            f"Messages: {len(messages)}"
        )
        logger.info("=" * 80)
        
        return AgentSalesFlowResponse(
            success=True,
            message="Agent sales flow executed successfully",
            data=response_data,
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        logger.info("=" * 80)
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        
        logger.error(
            f"[AGENT_API] ✗ Agent sales flow execution failed after "
            f"{execution_time:.3f}s: {e}",
            exc_info=True,
        )
        logger.info("=" * 80)
        
        raise HTTPException(
            status_code=500,
            detail=f"Agent sales flow execution failed: {str(e)}",
        )


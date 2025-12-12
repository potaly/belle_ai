"""Agent-based sales flow API endpoint."""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.graph.sales_graph import BusinessLogicError, run_sales_graph
from app.agents.planner_agent import build_final_plan, plan_sales_flow
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
    
    参数说明:
        request: Agent 销售流程请求
        db: 数据库会话
        
    返回值:
        AgentSalesFlowResponse: 包含商品信息、行为摘要、意图、消息等完整结果
        
    异常:
        HTTPException: 如果执行失败
        
    请求示例:
        ```json
        {
            "user_id": "user_001",
            "guide_id": "guide_001",
            "sku": "8WZ01CM1"
        }
        ```
        
    响应示例:
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
        initial_plan = await plan_sales_flow(context)
        logger.info(f"[AGENT_API] ✓ Initial plan generated: {initial_plan}")
        
        # Step 2.5: Build final plan with mandatory nodes enforcement
        logger.info("[AGENT_API] Step 2.5: Building final plan with mandatory nodes...")
        final_plan = build_final_plan(initial_plan, context)
        if final_plan != initial_plan:
            logger.info(
                f"[AGENT_API] Plan updated: initial={initial_plan}, "
                f"final={final_plan}"
            )
        logger.info(f"[AGENT_API] ✓ Final plan: {final_plan}")
        
        # Step 3: Execute sales graph with final plan
        logger.info("[AGENT_API] Step 3: Executing sales graph...")
        result_context = await run_sales_graph(context, plan=final_plan, enforce_mandatory=True)
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
        
        # Add intent information (must exist after execution)
        intent_level = result_context.intent_level
        if intent_level is None and result_context.user_id and result_context.behavior_summary:
            # This should not happen if mandatory nodes are enforced
            logger.warning(
                "[AGENT_API] ⚠ intent_level is None despite having user_id and behavior_summary. "
                "This indicates a business logic error."
            )
            intent_level = "unknown"  # Fallback value
        
        if intent_level:
            response_data["intent"] = {
                "level": intent_level,
                "reason": result_context.extra.get("intent_reason", ""),
            }
        
        # Add anti-disturb check results (must exist after execution)
        allowed = result_context.extra.get("allowed", False)
        anti_disturb_blocked = result_context.extra.get("anti_disturb_blocked", False)
        
        # Generate decision_reason (explainable decision)
        decision_reason = _generate_decision_reason(
            intent_level=intent_level,
            allowed=allowed,
            anti_disturb_blocked=anti_disturb_blocked,
            context=result_context,
        )
        
        response_data["allowed"] = allowed
        response_data["anti_disturb_blocked"] = anti_disturb_blocked
        response_data["decision_reason"] = decision_reason
        
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
        
        # Add execution plan (must be List[str])
        response_data["plan_used"] = final_plan
        
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
        
    except BusinessLogicError as e:
        execution_time = time.time() - start_time
        
        logger.error(
            f"[AGENT_API] ✗ Business logic error after {execution_time:.3f}s: {e.message}",
            exc_info=True,
        )
        logger.info("=" * 80)
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Business logic validation failed",
                "error_code": e.error_code,
                "message": e.message,
            },
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


def _generate_decision_reason(
    intent_level: str | None,
    allowed: bool,
    anti_disturb_blocked: bool,
    context: AgentContext,
) -> str:
    """
    生成决策原因说明（用于可解释性）。
    
    Args:
        intent_level: 用户意图级别
        allowed: 是否允许主动接触
        anti_disturb_blocked: 是否被反打扰机制阻止
        context: Agent context
    
    Returns:
        决策原因的文本说明
    """
    reasons = []
    
    # 意图级别说明
    if intent_level:
        intent_reason = context.extra.get("intent_reason", "")
        if intent_reason:
            reasons.append(f"用户意图级别为 {intent_level}：{intent_reason}")
        else:
            reasons.append(f"用户意图级别为 {intent_level}")
    else:
        reasons.append("无法确定用户意图级别（缺少行为数据）")
    
    # 反打扰决策说明
    if anti_disturb_blocked:
        reasons.append("反打扰机制阻止主动接触（低意图用户或系统策略）")
    elif allowed:
        reasons.append("反打扰检查通过，允许主动接触")
    else:
        reasons.append("反打扰检查未执行或结果未知")
    
    return "；".join(reasons)


"""Sales graph API endpoints."""
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
from app.schemas.sales_graph_schemas import (
    FollowupPlaybookItemSchema,
    MessageItemSchema,
    SalesGraphRequest,
    SalesGraphResponse,
    SalesSuggestionSchema,
    SendRecommendationSchema,
)
from app.services.sales_suggestion_service import (
    MessageItem,
    SalesSuggestion,
    SendRecommendation,
    build_suggestion_pack,
)

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
    
    参数说明:
        request: 销售图执行请求
        db: 数据库会话
        
    返回值:
        SalesGraphResponse: 执行结果，包含意图级别、生成的文案等信息
        
    请求示例:
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
        initial_plan: list[str] | None = None
        if request.use_custom_plan:
            logger.info("[API] Generating custom plan using planner")
            initial_plan = await plan_sales_flow(context)
            logger.info(f"[API] Generated initial plan: {initial_plan}")
            
            # 构建最终计划（确保包含强制节点）
            logger.info("[API] Building final plan with mandatory nodes enforcement")
            final_plan = build_final_plan(initial_plan, context)
            if final_plan != initial_plan:
                logger.info(
                    f"[API] Plan updated: initial={initial_plan}, final={final_plan}"
                )
        else:
            final_plan = None
        
        # 执行销售图
        logger.info("[API] Executing sales graph...")
        result_context = await run_sales_graph(
            context, plan=final_plan, enforce_mandatory=True
        )
        
        execution_time = time.time() - start_time
        
        # 构建响应数据
        rag_used = len(result_context.rag_chunks) > 0
        response_data: dict[str, Any] = {
            "user_id": result_context.user_id,
            "sku": result_context.sku,
            "intent_level": result_context.intent_level,
            "allowed": result_context.extra.get("allowed", False),
            "anti_disturb_blocked": result_context.extra.get("anti_disturb_blocked", False),
            "messages_count": len(result_context.messages),
            "rag_used": rag_used,  # RAG 是否被使用（True/False）
            "rag_chunks_count": len(result_context.rag_chunks),
            "rag_chunks": result_context.rag_chunks,  # 返回实际的 RAG chunks 内容
            "execution_time_seconds": round(execution_time, 3),
        }
        
        # Add RAG diagnostics (if available)
        rag_diagnostics = result_context.extra.get("rag_diagnostics")
        if rag_diagnostics:
            response_data["rag_diagnostics"] = rag_diagnostics
        else:
            # Default diagnostics if not available
            response_data["rag_diagnostics"] = {
                "retrieved_count": len(result_context.rag_chunks),
                "filtered_count": 0,
                "safe_count": len(result_context.rag_chunks),
                "filter_reasons": [],
            }
        
        # 添加计划信息（必须为 List[str]）
        if final_plan:
            response_data["plan_used"] = final_plan
        else:
            # 完整图流程：返回所有执行的节点
            response_data["plan_used"] = [
                "fetch_product",
                "fetch_behavior_summary",
                "classify_intent",
                "anti_disturb_check",
                "retrieve_rag",
                "generate_copy",
            ]
        
        # 添加决策原因（decision_reason）
        decision_reason = _generate_decision_reason(
            intent_level=result_context.intent_level,
            allowed=result_context.extra.get("allowed", False),
            anti_disturb_blocked=result_context.extra.get("anti_disturb_blocked", False),
            context=result_context,
        )
        response_data["decision_reason"] = decision_reason
        
        # 添加意图原因（保持向后兼容）
        if "intent_reason" in result_context.extra:
            response_data["intent_reason"] = result_context.extra["intent_reason"]
        
        # 添加最后一条消息（通常是生成的文案）- 保持向后兼容
        if result_context.messages:
            last_message = result_context.messages[-1]
            if last_message.get("role") == "assistant":
                response_data["final_message"] = last_message.get("content", "")
        
        # 生成销售建议包（V5.4.0+）
        try:
            if result_context.product and result_context.intent_level:
                logger.info("[API] Building sales suggestion pack...")
                suggestion = await build_suggestion_pack(result_context)
                
                # 转换为 schema
                suggestion_schema = SalesSuggestionSchema(
                    intent_level=suggestion.intent_level,
                    confidence=suggestion.confidence,
                    why_now=suggestion.why_now,
                    recommended_action=suggestion.recommended_action,
                    action_explanation=suggestion.action_explanation,
                    message_pack=[
                        MessageItemSchema(
                            type=msg.type,
                            strategy=msg.strategy,
                            message=msg.message,
                        )
                        for msg in suggestion.message_pack
                    ],
                    send_recommendation=SendRecommendationSchema(
                        suggested=suggestion.send_recommendation.suggested,
                        best_timing=suggestion.send_recommendation.best_timing,
                        note=suggestion.send_recommendation.note,
                        risk_level=suggestion.send_recommendation.risk_level,
                        next_step=suggestion.send_recommendation.next_step,
                    ),
                    followup_playbook=[
                        FollowupPlaybookItemSchema(
                            condition=item.condition,
                            reply=item.reply,
                        )
                        for item in suggestion.followup_playbook
                    ],
                )
                response_data["sales_suggestion"] = suggestion_schema.model_dump()
                
                # 确保 final_message 等于 primary message（向后兼容）
                if suggestion.message_pack:
                    primary_msg = next(
                        (msg for msg in suggestion.message_pack if msg.type == "primary"),
                        suggestion.message_pack[0],
                    )
                    response_data["final_message"] = primary_msg.message
                
                logger.info(
                    f"[API] ✓ Sales suggestion pack built: "
                    f"action={suggestion.recommended_action}, "
                    f"messages={len(suggestion.message_pack)}, "
                    f"suggested={suggestion.send_recommendation.suggested}"
                )
            else:
                logger.warning(
                    "[API] ⚠ Cannot build sales suggestion pack: "
                    "missing product or intent_level"
                )
        except Exception as e:
            logger.error(
                f"[API] ✗ Failed to build sales suggestion pack: {e}",
                exc_info=True,
            )
            # 不抛出异常，保持向后兼容
        
        # 添加商品信息摘要（如果有）
        if result_context.product:
            response_data["product_name"] = result_context.product.name
            response_data["product_price"] = float(result_context.product.price)
        
        logger.info(
            f"[API] ✓ Sales graph executed successfully in {execution_time:.3f}s. "
            f"Intent: {result_context.intent_level}, "
            f"Allowed: {result_context.extra.get('allowed')}, "
            f"Messages: {len(result_context.messages)}, "
            f"RAG chunks: {len(result_context.rag_chunks)}"
        )
        
        # 记录 RAG 是否被使用
        if result_context.rag_chunks:
            logger.info(
                f"[API] RAG chunks retrieved: {len(result_context.rag_chunks)} chunks. "
                f"First chunk preview: {result_context.rag_chunks[0][:100]}..."
            )
        else:
            logger.info("[API] No RAG chunks retrieved (may have been skipped due to low intent or RAG service unavailable)")
        logger.info("=" * 80)
        
        return SalesGraphResponse(
            success=True,
            message="Sales graph executed successfully",
            data=response_data,
        )
        
    except BusinessLogicError as e:
        execution_time = time.time() - start_time
        
        logger.error(
            f"[API] ✗ Business logic error after {execution_time:.3f}s: {e.message}",
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


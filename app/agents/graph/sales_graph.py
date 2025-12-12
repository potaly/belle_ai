"""LangGraph-based sales flow state machine."""
from __future__ import annotations

import logging
from typing import Literal, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.context import AgentContext
from app.agents.planner_agent import (
    TASK_ANTI_DISTURB_CHECK,
    TASK_CLASSIFY_INTENT,
    TASK_FETCH_BEHAVIOR_SUMMARY,
    TASK_FETCH_PRODUCT,
    TASK_GENERATE_COPY,
    TASK_RETRIEVE_RAG,
    build_final_plan,
)
from app.agents.tools.behavior_tool import fetch_behavior_summary
from app.agents.tools.copy_tool import generate_marketing_copy
from app.agents.tools.product_tool import fetch_product
from app.agents.tools.rag_tool import retrieve_rag
from app.agents.workers.copy_agent import generate_copy_node
from app.agents.workers.intent_agent import classify_intent_node
from app.agents.workers.sales_agent import anti_disturb_check_node
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """
    LangGraph state definition.
    
    Wraps AgentContext for LangGraph compatibility.
    """
    context: AgentContext


def _create_node_wrapper(node_func, node_name: str, requires_db: bool = False):
    """
    创建节点包装器，将 AgentContext 从 GraphState 中提取并传递。
    
    调用逻辑：
    - LangGraph 节点函数接收 state (GraphState)，需要提取 context
    - 执行节点函数后，将更新后的 context 放回 state
    - 如果节点需要 db session，会自动创建和关闭
    """
    async def wrapper(state: GraphState) -> GraphState:
        context = state["context"]
        
        try:
            if requires_db:
                # 需要数据库的节点（如 fetch_product, fetch_behavior_summary）
                db = SessionLocal()
                try:
                    context = await node_func(context, db)
                finally:
                    db.close()
            else:
                # 不需要数据库的节点
                context = await node_func(context)
            
            return {"context": context}
        except Exception as e:
            logger.error(
                f"[SALES_GRAPH] ✗ Node {node_name} failed: {e}",
                exc_info=True,
            )
            # 返回原始状态，避免状态损坏
            return state
    
    return wrapper


def _should_continue(state: GraphState) -> Literal["retrieve_rag", "generate_copy", END]:
    """
    条件路由函数：根据反打扰检查结果决定下一步。
    
    核心逻辑：
    - 如果反打扰检查通过（allowed=True），继续执行后续节点
    - 如果反打扰检查拒绝（allowed=False），提前结束流程
    - 如果意图级别为 low，跳过 RAG 检索，直接生成文案
    - 其他意图级别（high, medium, hesitating）会先检索 RAG，再生成文案
    """
    context = state["context"]
    allowed = context.extra.get("allowed", False)
    intent_level = context.intent_level
    
    logger.info(
        f"[SALES_GRAPH] Routing decision: allowed={allowed}, intent_level={intent_level}"
    )
    
    if not allowed:
        logger.info("[SALES_GRAPH] ✗ Anti-disturb check denied, ending early")
        return END
    
    # 检查是否需要检索 RAG
    if intent_level == "low":
        # 低意图跳过 RAG，直接生成文案
        logger.info(
            "[SALES_GRAPH] → Low intent detected, skipping RAG retrieval, "
            "going directly to generate_copy"
        )
        return "generate_copy"
    
    # 其他情况：先检索 RAG，再生成文案
    logger.info(
        f"[SALES_GRAPH] → Intent level '{intent_level}' requires RAG context, "
        "proceeding to retrieve_rag"
    )
    return "retrieve_rag"


def _create_sales_graph() -> StateGraph:
    """
    创建销售流程的 LangGraph 状态机。
    
    核心逻辑：
    - 构建节点：fetch_product → fetch_behavior_summary → classify_intent → 
               anti_disturb_check → (条件路由) → retrieve_rag → generate_copy → END
    - 条件路由：根据反打扰检查结果决定是否继续或提前结束
    """
    # 创建状态图
    graph = StateGraph(GraphState)
    
    # 添加节点（按执行顺序）
    # 节点1：获取商品信息
    graph.add_node(
        "fetch_product",
        _create_node_wrapper(fetch_product, "fetch_product", requires_db=True),
    )
    
    # 节点2：获取行为摘要
    graph.add_node(
        "fetch_behavior_summary",
        _create_node_wrapper(fetch_behavior_summary, "fetch_behavior_summary", requires_db=True),
    )
    
    # 节点3：分类意图
    graph.add_node(
        "classify_intent",
        _create_node_wrapper(classify_intent_node, "classify_intent"),
    )
    
    # 节点4：反打扰检查
    graph.add_node(
        "anti_disturb_check",
        _create_node_wrapper(anti_disturb_check_node, "anti_disturb_check"),
    )
    
    # 节点5：检索 RAG 上下文
    graph.add_node(
        "retrieve_rag",
        _create_node_wrapper(retrieve_rag, "retrieve_rag"),
    )
    
    # 节点6：生成文案
    graph.add_node(
        "generate_copy",
        _create_node_wrapper(generate_copy_node, "generate_copy"),
    )
    
    # 设置入口点
    graph.set_entry_point("fetch_product")
    
    # 添加边（顺序执行）
    graph.add_edge("fetch_product", "fetch_behavior_summary")
    graph.add_edge("fetch_behavior_summary", "classify_intent")
    graph.add_edge("classify_intent", "anti_disturb_check")
    
    # 条件边：根据反打扰检查结果决定下一步
    graph.add_conditional_edges(
        "anti_disturb_check",
        _should_continue,
        {
            "retrieve_rag": "retrieve_rag",
            "generate_copy": "generate_copy",
            END: END,
        },
    )
    
    # RAG 检索后生成文案
    graph.add_edge("retrieve_rag", "generate_copy")
    
    # 文案生成后结束
    graph.add_edge("generate_copy", END)
    
    # 编译图
    compiled_graph = graph.compile()
    
    logger.info("[SALES_GRAPH] Sales graph created and compiled successfully")
    return compiled_graph


# 全局图实例（延迟初始化）
_sales_graph: StateGraph | None = None


def get_sales_graph() -> StateGraph:
    """
    获取销售流程图的单例实例。
    
    Returns:
        Compiled StateGraph instance
    """
    global _sales_graph
    if _sales_graph is None:
        _sales_graph = _create_sales_graph()
    return _sales_graph


class BusinessLogicError(Exception):
    """
    业务逻辑错误：当强制业务步骤未执行或结果不完整时抛出。
    
    这个错误用于确保业务关键字段（如 intent_level）始终存在。
    """
    
    def __init__(self, message: str, error_code: str = "MISSING_MANDATORY_FIELD"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


async def run_sales_graph(
    context: AgentContext,
    plan: list[str] | None = None,
    enforce_mandatory: bool = True,
) -> AgentContext:
    """
    运行销售流程图。
    
    调用逻辑：
    - 如果提供了 plan，按计划顺序执行节点（忽略图中定义的顺序）
    - 如果没有 plan，使用图中定义的完整流程
    - 执行过程中，如果反打扰检查拒绝，会提前结束
    - 执行完成后，验证强制业务字段是否存在
    - 如果 intent_level 为 None，抛出 BusinessLogicError
    
    Args:
        context: 初始 Agent context
        plan: 可选的节点执行计划（如果为 None，使用完整流程）
    
    Returns:
        执行完成后的 AgentContext（保证包含 intent_level 和 allowed 字段）
    
    Raises:
        BusinessLogicError: 如果强制业务字段缺失（如 intent_level 为 None）
    
    Example:
        >>> context = AgentContext(user_id="user_001", sku="8WZ01CM1")
        >>> result = await run_sales_graph(context)
        >>> print(result.messages[-1]["content"])
        '这是一款舒适的跑鞋...'
    """
    logger.info("=" * 80)
    logger.info("[SALES_GRAPH] Starting sales graph execution")
    logger.info(f"[SALES_GRAPH] Context: user_id={context.user_id}, sku={context.sku}")
    
    # 如果启用了强制节点保护，确保计划包含所有强制节点
    final_plan = plan
    if plan and enforce_mandatory:
        logger.info("[SALES_GRAPH] Enforcing mandatory nodes in plan")
        final_plan = build_final_plan(plan, context)
        if final_plan != plan:
            logger.info(
                f"[SALES_GRAPH] Plan updated: original={plan}, "
                f"final={final_plan}"
            )
    
    if final_plan:
        logger.info(f"[SALES_GRAPH] Using plan: {' -> '.join(final_plan)}")
        # 如果提供了计划，按计划顺序执行节点
        result_context = await _execute_plan(context, final_plan)
    else:
        logger.info("[SALES_GRAPH] Using full graph flow")
        # 使用完整的图流程
        graph = get_sales_graph()
        # 打印当前执行的销售流程图名称（用于调试和监控）
        logger.info(f"[SALES_GRAPH] Compiled graph name: {graph.__class__.__name__}")
        # 获取所有需要执行的节点名并打印（调试用途）
        try:
            # 假设 graph.nodes 或 graph.get_nodes() 返回节点名或节点对象列表
            node_names = getattr(graph, "nodes", None)
            if node_names is None and hasattr(graph, "get_nodes"):
                node_names = graph.get_nodes()
            # 统一为名字（字符串）列表
            if node_names is not None:
                names = [n if isinstance(n, str) else getattr(n, "name", str(n)) for n in node_names]
                logger.info(f"[SALES_GRAPH] Node execution order: {' -> '.join(names)}")
        except Exception as e:
            logger.warning(f"[SALES_GRAPH] Failed to print node names: {e}")
        # 初始化状态
        initial_state: GraphState = {"context": context}
        
        # 执行图
        try:
            final_state = await graph.ainvoke(initial_state)
            result_context = final_state["context"]
        except Exception as e:
            logger.error(
                f"[SALES_GRAPH] ✗ Graph execution failed: {e}",
                exc_info=True,
            )
            logger.info("=" * 80)
            # 返回原始上下文，避免状态损坏
            return context
    
    # 执行后验证：确保强制业务字段存在
    _validate_mandatory_fields(result_context, plan)
    
    logger.info(
        f"[SALES_GRAPH] ✓ Graph execution completed. "
        f"Final context: messages={len(result_context.messages)}, "
        f"intent_level={result_context.intent_level}, "
        f"allowed={result_context.extra.get('allowed', None)}"
    )
    logger.info("=" * 80)
    
    return result_context


def _validate_mandatory_fields(context: AgentContext, plan: list[str] | None) -> None:
    """
    验证强制业务字段是否存在。
    
    核心规则：
    - intent_level 绝不能为 None（如果 user_id 和 behavior_summary 存在）
    - allowed / anti_disturb_blocked 必须存在（如果执行了 anti_disturb_check）
    
    Args:
        context: 执行完成后的 AgentContext
        plan: 执行的计划（用于生成错误消息）
    
    Raises:
        BusinessLogicError: 如果强制字段缺失
    """
    # 检查 intent_level
    if context.user_id and context.behavior_summary:
        # 如果有 user_id 和 behavior_summary，必须有 intent_level
        if context.intent_level is None:
            plan_str = " -> ".join(plan) if plan else "full_graph_flow"
            error_msg = (
                f"Mandatory field 'intent_level' is missing after graph execution. "
                f"This indicates that 'classify_intent' node was not executed or failed. "
                f"Plan executed: {plan_str}. "
                f"This is a business logic error and must be fixed."
            )
            logger.error(f"[SALES_GRAPH] ✗ {error_msg}")
            raise BusinessLogicError(error_msg, error_code="MISSING_INTENT_LEVEL")
    
    # 检查 allowed / anti_disturb_blocked（如果执行了反打扰检查）
    if context.intent_level is not None or context.behavior_summary is not None:
        # 如果有了意图级别或行为摘要，应该执行了反打扰检查
        if "allowed" not in context.extra:
            plan_str = " -> ".join(plan) if plan else "full_graph_flow"
            error_msg = (
                f"Mandatory field 'allowed' is missing after graph execution. "
                f"This indicates that 'anti_disturb_check' node was not executed or failed. "
                f"Plan executed: {plan_str}. "
                f"This is a business logic error and must be fixed."
            )
            logger.error(f"[SALES_GRAPH] ✗ {error_msg}")
            raise BusinessLogicError(error_msg, error_code="MISSING_ANTI_DISTURB_RESULT")
    
    logger.debug("[SALES_GRAPH] ✓ Mandatory fields validation passed")


async def _execute_plan(context: AgentContext, plan: list[str]) -> AgentContext:
    """
    按计划顺序执行节点（用于自定义计划）。
    
    核心逻辑：
    - 根据 plan 中的节点名称，按顺序调用对应的节点函数
    - 支持条件跳过（如果节点已执行过或条件不满足）
    - 如果反打扰检查拒绝，提前结束执行
    """
    logger.info(f"[SALES_GRAPH] Executing custom plan with {len(plan)} nodes")
    
    current_context = context
    
    for i, node_name in enumerate(plan, 1):
        logger.info(f"[SALES_GRAPH] Step {i}/{len(plan)}: {node_name}")
        
        try:
            # 根据节点名称执行对应的函数
            if node_name == TASK_FETCH_PRODUCT:
                db = SessionLocal()
                try:
                    current_context = await fetch_product(current_context, db)
                finally:
                    db.close()
                    
            elif node_name == TASK_FETCH_BEHAVIOR_SUMMARY:
                db = SessionLocal()
                try:
                    current_context = await fetch_behavior_summary(current_context, db)
                finally:
                    db.close()
                    
            elif node_name == TASK_CLASSIFY_INTENT:
                current_context = await classify_intent_node(current_context)
                
            elif node_name == TASK_ANTI_DISTURB_CHECK:
                current_context = await anti_disturb_check_node(current_context)
                # 检查是否应该提前结束
                allowed = current_context.extra.get("allowed", False)
                if not allowed:
                    logger.info(
                        "[SALES_GRAPH] Anti-disturb check denied, "
                        "ending plan execution early"
                    )
                    break
                    
            elif node_name == TASK_RETRIEVE_RAG:
                current_context = await retrieve_rag(current_context)
                
            elif node_name == TASK_GENERATE_COPY:
                current_context = await generate_copy_node(current_context)
                
            else:
                logger.warning(f"[SALES_GRAPH] Unknown node: {node_name}, skipping")
                continue
                
        except Exception as e:
            logger.error(
                f"[SALES_GRAPH] ✗ Node {node_name} failed: {e}",
                exc_info=True,
            )
            # 继续执行下一个节点，不中断整个流程
            continue
    
    logger.info("[SALES_GRAPH] ✓ Plan execution completed")
    return current_context


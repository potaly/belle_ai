"""Planner agent for determining task execution order."""
from __future__ import annotations

import logging
from typing import List, Optional

from app.agents.context import AgentContext
from app.services.intent_engine import (
    INTENT_HIGH,
    INTENT_HESITATING,
    INTENT_LOW,
    INTENT_MEDIUM,
    classify_intent,
)

logger = logging.getLogger(__name__)

# Task node names (must match tool/function names)
TASK_FETCH_PRODUCT = "fetch_product"
TASK_FETCH_BEHAVIOR_SUMMARY = "fetch_behavior_summary"
TASK_CLASSIFY_INTENT = "classify_intent"
TASK_ANTI_DISTURB_CHECK = "anti_disturb_check"
TASK_RETRIEVE_RAG = "retrieve_rag"
TASK_GENERATE_COPY = "generate_copy"
TASK_GENERATE_FOLLOWUP = "generate_followup"


async def plan_sales_flow(context: AgentContext) -> List[str]:
    """
    基于上下文和用户意图规划销售流程。
    
    调用逻辑：
    - 通常在 AgentRunner 执行计划前调用，由 PlannerAgent.plan() 内部调用
    - 前提条件：context 至少需要 sku，可选 user_id、product、behavior_summary 等
    - 调用场景：用户发起请求后，Agent 系统需要决定执行哪些任务时
    - 调用后：返回任务列表，由 AgentRunner.execute_plan() 按序执行
    - 规划策略：基于规则（rule_based），根据上下文状态动态决定任务顺序和是否跳过
    
    This planner uses rule-based logic to determine which tasks should be
    executed and in what order. It considers:
    - User intent level (high/medium/low/hesitating)
    - Anti-disturb mechanism (to avoid over-contacting users)
    - Required vs optional tasks
    
    Args:
        context: Agent context containing user_id, sku, and optionally
                 behavior_summary and intent_level
    
    Returns:
        List of task node names in execution order
    
    Example:
        >>> context = AgentContext(user_id="user_001", sku="8WZ01CM1")
        >>> plan = await plan_sales_flow(context)
        >>> print(plan)
        ['fetch_product', 'fetch_behavior_summary', 'classify_intent', ...]
    """
    logger.info("=" * 80)
    logger.info("[PLANNER] Planning sales flow")
    logger.info(
        f"[PLANNER] Context: user_id={context.user_id}, sku={context.sku}, "
        f"has_product={context.product is not None}, "
        f"has_behavior_summary={context.behavior_summary is not None}, "
        f"intent_level={context.intent_level}"
    )
    
    plan: List[str] = []
    
    # 核心规划逻辑：按依赖关系顺序添加任务，跳过已完成的步骤
    
    # 步骤1：加载商品信息（必需，后续步骤依赖）
    if not context.product:
        plan.append(TASK_FETCH_PRODUCT)
        logger.debug("[PLANNER] Added: fetch_product (required)")
    else:
        logger.debug("[PLANNER] Skipped: fetch_product (already loaded)")
    
    # 步骤2：获取行为摘要（需要 user_id 和 sku）
    if context.user_id and context.sku and not context.behavior_summary:
        plan.append(TASK_FETCH_BEHAVIOR_SUMMARY)
        logger.debug("[PLANNER] Added: fetch_behavior_summary (user data available)")
    elif not context.user_id:
        logger.debug("[PLANNER] Skipped: fetch_behavior_summary (no user_id)")
    else:
        logger.debug("[PLANNER] Skipped: fetch_behavior_summary (already loaded)")
    
    # 步骤3：分类意图（依赖行为摘要）
    if context.behavior_summary and not context.intent_level:
        plan.append(TASK_CLASSIFY_INTENT)
        logger.debug("[PLANNER] Added: classify_intent (behavior summary available)")
    elif not context.behavior_summary:
        logger.debug("[PLANNER] Skipped: classify_intent (no behavior summary)")
    else:
        logger.debug("[PLANNER] Skipped: classify_intent (already classified)")
    
    # 步骤4：反打扰检查（基于意图级别判断是否允许主动接触）
    intent_level = context.intent_level
    if not intent_level and context.behavior_summary:
        # 如果意图未分类但有行为数据，尝试预分类用于规划
        try:
            _, _ = classify_intent(context.behavior_summary)
            intent_level = None  # 将在 classify_intent 节点执行后设置
        except Exception:
            pass
    
    if intent_level or context.behavior_summary:
        plan.append(TASK_ANTI_DISTURB_CHECK)
        logger.debug("[PLANNER] Added: anti_disturb_check (intent/behavior available)")
    else:
        logger.debug("[PLANNER] Skipped: anti_disturb_check (no intent/behavior)")
    
    # 步骤5：检索 RAG 上下文（条件：低意图跳过，避免无效检索）
    should_retrieve_rag = _should_retrieve_rag(context, intent_level)
    if should_retrieve_rag:
        plan.append(TASK_RETRIEVE_RAG)
        logger.debug("[PLANNER] Added: retrieve_rag (intent level allows)")
    else:
        logger.debug(
            "[PLANNER] Skipped: retrieve_rag "
            f"(intent_level={intent_level}, low intent detected)"
        )
    
    # 步骤6：生成内容（文案或跟进话术，受反打扰机制控制）
    should_generate_content = _should_generate_content(context, intent_level)
    if should_generate_content:
        # 根据任务类型选择生成文案或跟进话术
        if context.extra.get("task_type") == "followup":
            plan.append(TASK_GENERATE_FOLLOWUP)
            logger.debug("[PLANNER] Added: generate_followup (task type specified)")
        else:
            plan.append(TASK_GENERATE_COPY)
            logger.debug("[PLANNER] Added: generate_copy (default)")
    else:
        logger.debug(
            "[PLANNER] Skipped: generate_copy/generate_followup "
            "(anti-disturb or low intent)"
        )
    
    logger.info(f"[PLANNER] ✓ Plan generated: {len(plan)} tasks")
    logger.info(f"[PLANNER] Plan: {' -> '.join(plan)}")
    logger.info("=" * 80)
    
    return plan


def _should_retrieve_rag(context: AgentContext, intent_level: Optional[str]) -> bool:
    """
    判断是否应该检索 RAG 上下文。
    
    核心规则：低意图用户跳过 RAG（避免无效检索，节省资源）
    
    Args:
        context: Agent context
        intent_level: Current intent level (if known)
    
    Returns:
        True if RAG should be retrieved, False otherwise
    """
    # 低意图用户跳过 RAG 检索
    if intent_level == INTENT_LOW:
        return False
    
    # If we have behavior summary but intent is not yet classified,
    # we'll classify it first, so allow RAG for now (will be refined later)
    if context.behavior_summary and not intent_level:
        # Default to allowing RAG (will be skipped if intent turns out to be low)
        return True
    
    # If no behavior data, allow RAG (general product search)
    if not context.behavior_summary:
        return True
    
    # For other intent levels (high, medium, hesitating), allow RAG
    return True


def _should_generate_content(
    context: AgentContext,
    intent_level: Optional[str],
) -> bool:
    """
    判断是否应该生成内容（文案或跟进话术）。
    
    核心规则：反打扰机制阻止时跳过；低意图用户默认跳过（除非强制生成）
    
    Args:
        context: Agent context
        intent_level: Current intent level (if known)
    
    Returns:
        True if content should be generated, False otherwise
    """
    # 反打扰机制已阻止，跳过内容生成
    if context.extra.get("anti_disturb_blocked", False):
        return False
    
    # 低意图用户默认跳过，除非明确要求生成
    if intent_level == INTENT_LOW:
        return context.extra.get("force_generate", False)
    
    # Default: allow content generation
    return True


class PlannerAgent:
    """
    Planner agent for determining task execution order.
    
    This class provides a more structured interface for planning,
    with support for different planning strategies (rule-based, LLM-based).
    """
    
    def __init__(self, strategy: str = "rule_based") -> None:
        """
        Initialize planner agent.
        
        Args:
            strategy: Planning strategy ("rule_based" or "llm_based")
        """
        self.strategy = strategy
        logger.info(f"[PLANNER] Initialized with strategy: {strategy}")
    
    async def plan(
        self,
        context: AgentContext,
        user_intent: Optional[str] = None,
    ) -> List[str]:
        """
        Generate a plan based on context and user intent.
        
        Args:
            context: Agent context
            user_intent: Optional explicit user intent description
                        (e.g., "帮我分析顾客并生成促单话术")
        
        Returns:
            List of task node names in execution order
        """
        # Store user intent in context if provided
        if user_intent:
            context.extra["user_intent"] = user_intent
            logger.info(f"[PLANNER] User intent: {user_intent}")
        
        if self.strategy == "rule_based":
            return await plan_sales_flow(context)
        elif self.strategy == "llm_based":
            # Future: LLM-based planning
            logger.warning("[PLANNER] LLM-based planning not yet implemented, using rule-based")
            return await plan_sales_flow(context)
        else:
            logger.warning(
                f"[PLANNER] Unknown strategy: {self.strategy}, using rule-based"
            )
            return await plan_sales_flow(context)
    
    def get_available_tasks(self) -> List[str]:
        """
        Get list of all available task names.
        
        Returns:
            List of task node names
        """
        return [
            TASK_FETCH_PRODUCT,
            TASK_FETCH_BEHAVIOR_SUMMARY,
            TASK_CLASSIFY_INTENT,
            TASK_ANTI_DISTURB_CHECK,
            TASK_RETRIEVE_RAG,
            TASK_GENERATE_COPY,
            TASK_GENERATE_FOLLOWUP,
        ]


# Convenience function
async def create_plan(
    context: AgentContext,
    user_intent: Optional[str] = None,
) -> List[str]:
    """
    Convenience function to create a plan.
    
    Args:
        context: Agent context
        user_intent: Optional user intent description
    
    Returns:
        List of task node names
    """
    planner = PlannerAgent(strategy="rule_based")
    return await planner.plan(context, user_intent)


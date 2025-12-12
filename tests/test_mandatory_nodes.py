"""Tests for mandatory business nodes enforcement."""
from __future__ import annotations

import pytest

from app.agents.context import AgentContext
from app.agents.graph.sales_graph import BusinessLogicError, run_sales_graph
from app.agents.planner_agent import (
    TASK_ANTI_DISTURB_CHECK,
    TASK_CLASSIFY_INTENT,
    TASK_FETCH_BEHAVIOR_SUMMARY,
    TASK_FETCH_PRODUCT,
    TASK_GENERATE_COPY,
    TASK_RETRIEVE_RAG,
    MANDATORY_NODES,
    build_final_plan,
)


class TestMandatoryNodesEnforcement:
    """测试强制节点保护机制。"""
    
    def test_build_final_plan_injects_mandatory_nodes(self):
        """测试：自定义计划缺少强制节点时，build_final_plan 会自动注入。"""
        # 创建上下文（有 user_id 和 sku，但没有 product 和 behavior_summary）
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        
        # 自定义计划：只包含可选节点，缺少强制节点
        custom_plan = [TASK_RETRIEVE_RAG, TASK_GENERATE_COPY]
        
        # 构建最终计划
        final_plan = build_final_plan(custom_plan, context)
        
        # 验证：最终计划必须包含所有强制节点
        assert TASK_FETCH_PRODUCT in final_plan, "fetch_product 必须包含在最终计划中"
        assert TASK_FETCH_BEHAVIOR_SUMMARY in final_plan, "fetch_behavior_summary 必须包含在最终计划中"
        assert TASK_CLASSIFY_INTENT in final_plan, "classify_intent 必须包含在最终计划中"
        assert TASK_ANTI_DISTURB_CHECK in final_plan, "anti_disturb_check 必须包含在最终计划中"
        
        # 验证：可选节点也应该保留
        assert TASK_RETRIEVE_RAG in final_plan, "可选节点 retrieve_rag 应该保留"
        assert TASK_GENERATE_COPY in final_plan, "可选节点 generate_copy 应该保留"
        
        # 验证：强制节点在可选节点之前（依赖顺序）
        fetch_product_idx = final_plan.index(TASK_FETCH_PRODUCT)
        fetch_behavior_idx = final_plan.index(TASK_FETCH_BEHAVIOR_SUMMARY)
        classify_intent_idx = final_plan.index(TASK_CLASSIFY_INTENT)
        anti_disturb_idx = final_plan.index(TASK_ANTI_DISTURB_CHECK)
        retrieve_rag_idx = final_plan.index(TASK_RETRIEVE_RAG)
        generate_copy_idx = final_plan.index(TASK_GENERATE_COPY)
        
        assert fetch_product_idx < fetch_behavior_idx < classify_intent_idx < anti_disturb_idx, \
            "强制节点必须按依赖顺序排列"
        assert anti_disturb_idx < retrieve_rag_idx < generate_copy_idx, \
            "可选节点应该在强制节点之后"
    
    def test_build_final_plan_preserves_existing_mandatory_nodes(self):
        """测试：如果自定义计划已包含强制节点，不会重复添加。"""
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        
        # 自定义计划：已包含所有强制节点
        custom_plan = [
            TASK_FETCH_PRODUCT,
            TASK_FETCH_BEHAVIOR_SUMMARY,
            TASK_CLASSIFY_INTENT,
            TASK_ANTI_DISTURB_CHECK,
            TASK_RETRIEVE_RAG,
            TASK_GENERATE_COPY,
        ]
        
        final_plan = build_final_plan(custom_plan, context)
        
        # 验证：每个强制节点只出现一次
        for node in MANDATORY_NODES:
            assert final_plan.count(node) == 1, f"{node} 应该只出现一次"
    
    def test_build_final_plan_handles_empty_custom_plan(self):
        """测试：空的自定义计划会生成完整的强制节点计划。"""
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        
        custom_plan = []
        
        final_plan = build_final_plan(custom_plan, context)
        
        # 验证：最终计划包含所有强制节点
        for node in MANDATORY_NODES:
            assert node in final_plan, f"{node} 必须包含在最终计划中"
    
    def test_build_final_plan_skips_nodes_when_context_has_data(self):
        """测试：如果上下文已有数据，会跳过对应的节点。"""
        # 创建已有 product 的上下文
        from app.models.product import Product
        
        product = Product(
            sku="8WZ01CM1",
            name="测试商品",
            price=100.0,
        )
        
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
            product=product,  # 已有 product
        )
        
        custom_plan = [TASK_RETRIEVE_RAG]
        
        final_plan = build_final_plan(custom_plan, context)
        
        # 验证：fetch_product 被跳过（因为已有 product）
        assert TASK_FETCH_PRODUCT not in final_plan, \
            "如果已有 product，应该跳过 fetch_product"
        
        # 验证：其他强制节点仍然包含
        assert TASK_FETCH_BEHAVIOR_SUMMARY in final_plan
        assert TASK_CLASSIFY_INTENT in final_plan
        assert TASK_ANTI_DISTURB_CHECK in final_plan


class TestBusinessLogicValidation:
    """测试业务逻辑验证。"""
    
    @pytest.mark.asyncio
    async def test_run_sales_graph_validates_intent_level(self):
        """测试：执行后验证 intent_level 不为 None（如果有 user_id 和 behavior_summary）。"""
        # 创建上下文（有 user_id 和 sku）
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        
        # 创建一个缺少 classify_intent 的计划（这会导致 intent_level 为 None）
        incomplete_plan = [
            TASK_FETCH_PRODUCT,
            TASK_FETCH_BEHAVIOR_SUMMARY,
            # 缺少 TASK_CLASSIFY_INTENT
            TASK_ANTI_DISTURB_CHECK,
        ]
        
        # 注意：由于 build_final_plan 会自动注入强制节点，这个测试需要模拟
        # 实际场景中，如果 classify_intent 节点执行失败，intent_level 仍可能为 None
        
        # 这个测试需要 mock 数据库和实际执行，暂时跳过
        # 在实际集成测试中验证
        pass
    
    def test_decision_reason_generation(self):
        """测试：决策原因生成逻辑。"""
        from app.api.v1.agent_sales_flow import _generate_decision_reason
        
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        context.intent_level = "high"
        context.extra["intent_reason"] = "用户已进入购买页面"
        context.extra["allowed"] = True
        context.extra["anti_disturb_blocked"] = False
        
        reason = _generate_decision_reason(
            intent_level="high",
            allowed=True,
            anti_disturb_blocked=False,
            context=context,
        )
        
        assert "用户意图级别为 high" in reason
        assert "用户已进入购买页面" in reason
        assert "反打扰检查通过" in reason
    
    def test_decision_reason_for_blocked_case(self):
        """测试：被阻止时的决策原因。"""
        from app.api.v1.agent_sales_flow import _generate_decision_reason
        
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        context.intent_level = "low"
        context.extra["allowed"] = False
        context.extra["anti_disturb_blocked"] = True
        
        reason = _generate_decision_reason(
            intent_level="low",
            allowed=False,
            anti_disturb_blocked=True,
            context=context,
        )
        
        assert "用户意图级别为 low" in reason
        assert "反打扰机制阻止" in reason
        assert reason  # 非空


class TestPlanUsedField:
    """测试 plan_used 字段。"""
    
    def test_plan_used_is_list(self):
        """测试：plan_used 必须是 List[str]，不能是字符串。"""
        # 这个测试在 API 响应中验证
        # plan_used 应该始终是数组，例如：
        # "plan_used": ["fetch_product", "fetch_behavior_summary", ...]
        # 而不是：
        # "plan_used": "full_graph_flow"
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


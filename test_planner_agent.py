"""Test script for planner agent."""
import asyncio
import sys

# Add project root to path
sys.path.insert(0, ".")

from app.agents.context import AgentContext
from app.agents.planner_agent import PlannerAgent, plan_sales_flow


async def test_planner_basic():
    """Test basic planner functionality."""
    print("=" * 80)
    print("测试 Planner Agent - 基础功能")
    print("=" * 80)
    
    # Test 1: Empty context (minimal plan)
    print("\n[测试 1] 空上下文（只有 SKU）")
    context = AgentContext(sku="8WZ01CM1")
    plan = await plan_sales_flow(context)
    print(f"生成的计划: {plan}")
    print(f"计划长度: {len(plan)}")
    
    # Test 2: Context with user_id
    print("\n[测试 2] 包含 user_id 的上下文")
    context = AgentContext(user_id="user_001", sku="8WZ01CM1")
    plan = await plan_sales_flow(context)
    print(f"生成的计划: {plan}")
    print(f"计划长度: {len(plan)}")
    
    # Test 3: Context with behavior summary (low intent)
    print("\n[测试 3] 包含行为摘要（低意图）")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 1,
            "max_stay_seconds": 5,
            "avg_stay_seconds": 5.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "event_types": ["browse"],
        },
        intent_level="low",
    )
    plan = await plan_sales_flow(context)
    print(f"生成的计划: {plan}")
    print(f"计划长度: {len(plan)}")
    print(f"是否包含 retrieve_rag: {'retrieve_rag' in plan}")
    
    # Test 4: Context with behavior summary (high intent)
    print("\n[测试 4] 包含行为摘要（高意图）")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 3,
            "max_stay_seconds": 45,
            "avg_stay_seconds": 30.0,
            "has_enter_buy_page": True,
            "has_favorite": True,
            "event_types": ["browse", "enter_buy_page", "favorite"],
        },
        intent_level="high",
    )
    plan = await plan_sales_flow(context)
    print(f"生成的计划: {plan}")
    print(f"计划长度: {len(plan)}")
    print(f"是否包含 retrieve_rag: {'retrieve_rag' in plan}")
    
    # Test 5: Context with product already loaded
    print("\n[测试 5] 商品已加载的上下文")
    from app.models.product import Product
    
    product = Product(
        id=1,
        sku="8WZ01CM1",
        name="舒适跑鞋",
        price=398.00,
        tags=["舒适", "轻便"],
    )
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        product=product,
    )
    plan = await plan_sales_flow(context)
    print(f"生成的计划: {plan}")
    print(f"是否包含 fetch_product: {'fetch_product' in plan}")
    
    print("\n" + "=" * 80)
    print("基础功能测试完成")
    print("=" * 80)


async def test_planner_agent_class():
    """Test PlannerAgent class."""
    print("\n" + "=" * 80)
    print("测试 PlannerAgent 类")
    print("=" * 80)
    
    planner = PlannerAgent(strategy="rule_based")
    print(f"✓ PlannerAgent 创建成功，策略: {planner.strategy}")
    
    # Get available tasks
    tasks = planner.get_available_tasks()
    print(f"\n可用任务列表 ({len(tasks)} 个):")
    for i, task in enumerate(tasks, 1):
        print(f"  {i}. {task}")
    
    # Test planning with user intent
    print("\n[测试] 带用户意图的规划")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
    )
    user_intent = "帮我分析顾客并生成促单话术"
    plan = await planner.plan(context, user_intent=user_intent)
    print(f"用户意图: {user_intent}")
    print(f"生成的计划: {plan}")
    print(f"计划步骤数: {len(plan)}")
    
    print("\n" + "=" * 80)
    print("PlannerAgent 类测试完成")
    print("=" * 80)


async def test_planner_rules():
    """Test planner rules."""
    print("\n" + "=" * 80)
    print("测试 Planner 规则")
    print("=" * 80)
    
    # Rule 1: Low intent should skip RAG
    print("\n[规则测试 1] 低意图应跳过 RAG")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 1,
            "max_stay_seconds": 3,
            "avg_stay_seconds": 3.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "event_types": ["browse"],
        },
        intent_level="low",
    )
    plan = await plan_sales_flow(context)
    has_rag = "retrieve_rag" in plan
    print(f"计划: {plan}")
    print(f"包含 RAG: {has_rag}")
    print(f"✓ 规则验证: {'通过' if not has_rag else '失败'}")
    
    # Rule 2: High intent should include RAG
    print("\n[规则测试 2] 高意图应包含 RAG")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 3,
            "max_stay_seconds": 50,
            "avg_stay_seconds": 35.0,
            "has_enter_buy_page": True,
            "has_favorite": True,
            "event_types": ["browse", "enter_buy_page", "favorite"],
        },
        intent_level="high",
    )
    plan = await plan_sales_flow(context)
    has_rag = "retrieve_rag" in plan
    print(f"计划: {plan}")
    print(f"包含 RAG: {has_rag}")
    print(f"✓ 规则验证: {'通过' if has_rag else '失败'}")
    
    # Rule 3: Anti-disturb should block content generation
    print("\n[规则测试 3] 反打扰机制应阻止内容生成")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 1,
            "max_stay_seconds": 2,
            "avg_stay_seconds": 2.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "event_types": ["browse"],
        },
        intent_level="low",
        extra={"anti_disturb_blocked": True},
    )
    plan = await plan_sales_flow(context)
    has_copy = "generate_copy" in plan or "generate_followup" in plan
    print(f"计划: {plan}")
    print(f"包含内容生成: {has_copy}")
    print(f"✓ 规则验证: {'通过' if not has_copy else '失败'}")
    
    print("\n" + "=" * 80)
    print("规则测试完成")
    print("=" * 80)


async def main():
    """Run all tests."""
    await test_planner_basic()
    await test_planner_agent_class()
    await test_planner_rules()
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


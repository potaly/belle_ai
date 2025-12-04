"""Test script for sales graph."""
import asyncio
import sys

# Add project root to path
sys.path.insert(0, ".")

from app.agents.context import AgentContext
from app.agents.graph.sales_graph import run_sales_graph
from app.agents.planner_agent import plan_sales_flow


async def test_sales_graph():
    """Test sales graph execution."""
    print("=" * 80)
    print("测试 Sales Graph")
    print("=" * 80)
    
    # Test case 1: Full graph flow
    print("\n[测试用例 1] 完整图流程")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
    )
    
    result = await run_sales_graph(context, plan=None)
    
    print(f"\n✓ 图执行完成:")
    print(f"  - 意图级别: {result.intent_level}")
    print(f"  - 允许接触: {result.extra.get('allowed')}")
    print(f"  - 消息数量: {len(result.messages)}")
    if result.messages:
        print(f"  - 最后消息: {result.messages[-1]['content'][:50]}...")
    
    # Test case 2: Custom plan
    print("\n[测试用例 2] 自定义计划")
    context2 = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
    )
    
    # Generate plan
    plan = await plan_sales_flow(context2)
    print(f"生成的计划: {plan}")
    
    # Execute with plan
    result2 = await run_sales_graph(context2, plan=plan)
    
    print(f"\n✓ 计划执行完成:")
    print(f"  - 意图级别: {result2.intent_level}")
    print(f"  - 消息数量: {len(result2.messages)}")
    
    # Test case 3: Low intent (should skip RAG and end early)
    print("\n[测试用例 3] 低意图用户（应提前结束）")
    context3 = AgentContext(
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
    
    result3 = await run_sales_graph(context3, plan=None)
    
    print(f"\n✓ 低意图流程执行完成:")
    print(f"  - 意图级别: {result3.intent_level}")
    print(f"  - 允许接触: {result3.extra.get('allowed')}")
    print(f"  - RAG片段数: {len(result3.rag_chunks)}")
    print(f"  - 消息数量: {len(result3.messages)}")
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_sales_graph())


"""Test script for agent framework."""
import asyncio
import sys

# Add project root to path
sys.path.insert(0, ".")

from app.agents import AgentContext, AgentRunner
from app.models.product import Product


async def test_agent_context():
    """Test AgentContext functionality."""
    print("=" * 80)
    print("测试 AgentContext")
    print("=" * 80)
    
    # Create context
    context = AgentContext(
        user_id="user_001",
        guide_id="guide_001",
        sku="8WZ01CM1",
        intent_level="high",
    )
    
    print(f"✓ Context created: {context}")
    
    # Add messages
    context.add_message("user", "我想买一双舒适的运动鞋")
    context.add_message("assistant", "好的，我为您推荐这款舒适跑鞋...")
    context.add_message("user", "价格是多少？")
    
    print(f"✓ Added {len(context.messages)} messages")
    
    # Get latest messages
    latest = context.get_latest(2)
    print(f"✓ Latest 2 messages: {len(latest)}")
    for msg in latest:
        print(f"  - {msg['role']}: {msg['content']}")
    
    # Test to_prompt
    prompt = context.to_prompt()
    print(f"\n✓ Generated prompt ({len(prompt)} chars):")
    print("-" * 80)
    print(prompt[:200] + "..." if len(prompt) > 200 else prompt)
    print("-" * 80)
    
    # Test copy
    context_copy = context.copy()
    context_copy.add_message("assistant", "这是复制的上下文")
    print(f"\n✓ Original messages: {len(context.messages)}")
    print(f"✓ Copied messages: {len(context_copy.messages)}")
    
    print("\n" + "=" * 80)
    print("AgentContext 测试完成")
    print("=" * 80)


async def test_agent_runner():
    """Test AgentRunner functionality."""
    print("\n" + "=" * 80)
    print("测试 AgentRunner")
    print("=" * 80)
    
    # Create runner
    runner = AgentRunner(enable_logging=True)
    print("✓ AgentRunner created")
    
    # Create context
    context = AgentContext(user_id="user_001", sku="8WZ01CM1")
    
    # Define test nodes
    async def node1(context: AgentContext) -> AgentContext:
        """First test node."""
        context.add_message("system", "开始处理用户请求")
        context.extra["step"] = 1
        return context
    
    async def node2(context: AgentContext) -> AgentContext:
        """Second test node."""
        context.add_message("assistant", "正在分析商品信息...")
        context.extra["step"] = 2
        return context
    
    async def node3(context: AgentContext) -> AgentContext:
        """Third test node."""
        context.add_message("assistant", "分析完成，生成推荐")
        context.extra["step"] = 3
        return context
    
    # Test single node execution
    print("\n--- 测试单个节点执行 ---")
    result = await runner.run_node(node1, context, "node1")
    print(f"✓ Node executed, extra: {result.extra}")
    
    # Test plan execution
    print("\n--- 测试计划执行 ---")
    node_registry = {
        "node1": node1,
        "node2": node2,
        "node3": node3,
    }
    
    plan = ["node1", "node2", "node3"]
    final_context = await runner.execute_plan(plan, context, node_registry)
    
    print(f"\n✓ Plan executed successfully")
    print(f"  - Messages: {len(final_context.messages)}")
    print(f"  - Extra: {final_context.extra}")
    print(f"  - Final step: {final_context.extra.get('step')}")
    
    print("\n" + "=" * 80)
    print("AgentRunner 测试完成")
    print("=" * 80)


async def test_integration():
    """Test integration with Product model."""
    print("\n" + "=" * 80)
    print("测试集成（Product + Context）")
    print("=" * 80)
    
    # Create mock product
    product = Product(
        id=1,
        sku="8WZ01CM1",
        name="舒适跑鞋",
        price=398.00,
        tags=["舒适", "轻便", "时尚"],
        description="这是一款舒适的跑鞋，适合日常运动",
    )
    
    # Create context with product
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        product=product,
        intent_level="high",
        behavior_summary={
            "visit_count": 2,
            "max_stay_seconds": 30,
            "avg_stay_seconds": 20.0,
            "has_enter_buy_page": True,
        },
        rag_chunks=[
            "这是一款红色的舒适跑鞋，适合四季运动穿着",
            "商品价格：398元，材质为网面，具有透气轻便的特点",
        ],
    )
    
    context.add_message("user", "我想买一双舒适的运动鞋")
    
    # Generate prompt
    prompt = context.to_prompt()
    print("✓ Context with product created")
    print(f"✓ Generated prompt ({len(prompt)} chars)")
    print("\n完整 Prompt:")
    print("-" * 80)
    print(prompt)
    print("-" * 80)
    
    print("\n" + "=" * 80)
    print("集成测试完成")
    print("=" * 80)


async def main():
    """Run all tests."""
    await test_agent_context()
    await test_agent_runner()
    await test_integration()
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


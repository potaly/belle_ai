"""Test script for worker agents."""
import asyncio
import sys

# Add project root to path
sys.path.insert(0, ".")

from app.agents.context import AgentContext
from app.agents.workers import (
    anti_disturb_check_node,
    classify_intent_node,
    generate_copy_node,
)


async def test_intent_agent():
    """Test intent agent."""
    print("=" * 80)
    print("测试 IntentAgent")
    print("=" * 80)
    
    # Create context with behavior summary
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 2,
            "max_stay_seconds": 30,
            "avg_stay_seconds": 20.0,
            "total_stay_seconds": 40,
            "has_enter_buy_page": True,
            "has_favorite": False,
            "has_share": False,
            "has_click_size_chart": False,
            "event_types": ["browse", "enter_buy_page"],
        },
    )
    
    print(f"初始上下文: intent_level={context.intent_level}")
    
    # Classify intent
    context = await classify_intent_node(context)
    
    print(f"\n✓ 意图分类完成:")
    print(f"  - 意图级别: {context.intent_level}")
    print(f"  - 原因: {context.extra.get('intent_reason', 'N/A')}")
    
    print("=" * 80)


async def test_sales_agent():
    """Test sales agent."""
    print("\n" + "=" * 80)
    print("测试 SalesAgent")
    print("=" * 80)
    
    # Test case 1: High intent
    print("\n[测试用例 1] 高意图用户")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        intent_level="high",
    )
    context = await anti_disturb_check_node(context)
    print(f"  允许接触: {context.extra.get('allowed')}")
    print(f"  反打扰阻止: {context.extra.get('anti_disturb_blocked')}")
    
    # Test case 2: Low intent
    print("\n[测试用例 2] 低意图用户")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        intent_level="low",
    )
    context = await anti_disturb_check_node(context)
    print(f"  允许接触: {context.extra.get('allowed')}")
    print(f"  反打扰阻止: {context.extra.get('anti_disturb_blocked')}")
    
    # Test case 3: Force allow
    print("\n[测试用例 3] 强制允许")
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        intent_level="low",
        extra={"force_allow": True},
    )
    context = await anti_disturb_check_node(context)
    print(f"  允许接触: {context.extra.get('allowed')}")
    print(f"  反打扰阻止: {context.extra.get('anti_disturb_blocked')}")
    
    print("=" * 80)


async def test_copy_agent():
    """Test copy agent."""
    print("\n" + "=" * 80)
    print("测试 CopyAgent")
    print("=" * 80)
    
    from app.models.product import Product
    
    # Create context with product
    product = Product(
        id=1,
        sku="8WZ01CM1",
        name="舒适跑鞋",
        price=398.00,
        tags=["舒适", "轻便", "时尚"],
        description="这是一款舒适的跑鞋，适合日常运动",
    )
    
    context = AgentContext(
        sku="8WZ01CM1",
        product=product,
        rag_chunks=[
            "这是一款红色的舒适跑鞋，适合四季运动穿着",
            "商品价格：398元，材质为网面，具有透气轻便的特点",
        ],
    )
    
    print(f"商品: {context.product.name}")
    print(f"RAG片段: {len(context.rag_chunks)} 个")
    
    # Generate copy
    context = await generate_copy_node(context)
    
    print(f"\n✓ 文案生成完成:")
    if context.messages:
        last_message = context.messages[-1]
        print(f"  - 角色: {last_message['role']}")
        print(f"  - 内容: {last_message['content']}")
    
    print("=" * 80)


async def test_integration():
    """Test full integration."""
    print("\n" + "=" * 80)
    print("测试完整集成流程")
    print("=" * 80)
    
    from app.models.product import Product
    
    # Create context
    context = AgentContext(
        user_id="user_001",
        sku="8WZ01CM1",
        behavior_summary={
            "visit_count": 2,
            "max_stay_seconds": 30,
            "avg_stay_seconds": 20.0,
            "has_enter_buy_page": True,
            "has_favorite": False,
            "event_types": ["browse", "enter_buy_page"],
        },
    )
    
    # Add product
    product = Product(
        id=1,
        sku="8WZ01CM1",
        name="舒适跑鞋",
        price=398.00,
        tags=["舒适", "轻便"],
    )
    context.product = product
    
    print("步骤 1: 分类意图...")
    context = await classify_intent_node(context)
    print(f"  ✓ 意图级别: {context.intent_level}")
    
    print("\n步骤 2: 反打扰检查...")
    context = await anti_disturb_check_node(context)
    print(f"  ✓ 允许接触: {context.extra.get('allowed')}")
    
    print("\n步骤 3: 生成文案...")
    context = await generate_copy_node(context)
    if context.messages:
        print(f"  ✓ 生成的文案: {context.messages[-1]['content'][:50]}...")
    
    print("\n" + "=" * 80)
    print("完整流程测试成功！")
    print("=" * 80)


async def main():
    """Run all tests."""
    await test_intent_agent()
    await test_sales_agent()
    await test_copy_agent()
    await test_integration()
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


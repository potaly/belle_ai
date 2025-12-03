"""Test script for agent tools."""
import asyncio
import sys

# Add project root to path
sys.path.insert(0, ".")

from app.agents.context import AgentContext
from app.agents.tools import (
    fetch_behavior_summary,
    fetch_product,
    generate_marketing_copy,
    retrieve_rag,
)
from app.core.database import SessionLocal
from app.schemas.copy_schemas import CopyStyle


async def test_product_tool():
    """Test product tool."""
    print("=" * 80)
    print("测试 ProductTool")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        context = AgentContext(sku="8WZ01CM1")
        print(f"初始上下文: {context}")
        
        context = await fetch_product(context, db)
        
        print(f"\n✓ 商品加载成功:")
        print(f"  - 商品名称: {context.product.name}")
        print(f"  - 商品价格: {context.product.price}元")
        print(f"  - 商品标签: {context.product.tags}")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    print("=" * 80)


async def test_behavior_tool():
    """Test behavior tool."""
    print("\n" + "=" * 80)
    print("测试 BehaviorTool")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        context = AgentContext(user_id="user_001", sku="8WZ01CM1")
        print(f"初始上下文: user_id={context.user_id}, sku={context.sku}")
        
        context = await fetch_behavior_summary(context, db, limit=50)
        
        if context.behavior_summary:
            summary = context.behavior_summary
            print(f"\n✓ 行为摘要生成成功:")
            print(f"  - 访问次数: {summary['visit_count']}")
            print(f"  - 最大停留: {summary['max_stay_seconds']}秒")
            print(f"  - 平均停留: {summary['avg_stay_seconds']:.1f}秒")
            print(f"  - 进入购买页: {summary['has_enter_buy_page']}")
            print(f"  - 收藏: {summary['has_favorite']}")
        else:
            print("\n✓ 无行为记录（返回空摘要）")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    print("=" * 80)


async def test_rag_tool():
    """Test RAG tool."""
    print("\n" + "=" * 80)
    print("测试 RAGTool")
    print("=" * 80)
    
    try:
        # First fetch product
        db = SessionLocal()
        context = AgentContext(sku="8WZ01CM1")
        context = await fetch_product(context, db)
        db.close()
        
        print(f"商品: {context.product.name}")
        
        # Then retrieve RAG
        context = await retrieve_rag(context, top_k=3)
        
        print(f"\n✓ RAG检索成功:")
        print(f"  - 检索到 {len(context.rag_chunks)} 个相关片段")
        for i, chunk in enumerate(context.rag_chunks[:3], 1):
            print(f"  {i}. {chunk[:80]}...")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)


async def test_copy_tool():
    """Test copy tool."""
    print("\n" + "=" * 80)
    print("测试 CopyTool")
    print("=" * 80)
    
    try:
        # Setup context with product and RAG
        db = SessionLocal()
        context = AgentContext(sku="8WZ01CM1")
        
        # Fetch product
        context = await fetch_product(context, db)
        print(f"商品: {context.product.name}")
        
        # Retrieve RAG
        context = await retrieve_rag(context, top_k=3)
        print(f"RAG片段: {len(context.rag_chunks)} 个")
        
        db.close()
        
        # Generate copy
        context = await generate_marketing_copy(context, style=CopyStyle.natural)
        
        print(f"\n✓ 文案生成成功:")
        if context.messages:
            last_message = context.messages[-1]
            print(f"  - 角色: {last_message['role']}")
            print(f"  - 内容: {last_message['content']}")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)


async def test_integration():
    """Test full integration of all tools."""
    print("\n" + "=" * 80)
    print("测试完整集成流程")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        # Create initial context
        context = AgentContext(
            user_id="user_001",
            sku="8WZ01CM1",
        )
        
        print("步骤 1: 加载商品信息...")
        context = await fetch_product(context, db)
        print(f"  ✓ 商品: {context.product.name}")
        
        print("\n步骤 2: 获取行为摘要...")
        context = await fetch_behavior_summary(context, db)
        if context.behavior_summary:
            print(f"  ✓ 访问次数: {context.behavior_summary['visit_count']}")
        
        print("\n步骤 3: 检索RAG上下文...")
        context = await retrieve_rag(context, top_k=3)
        print(f"  ✓ RAG片段: {len(context.rag_chunks)} 个")
        
        print("\n步骤 4: 生成营销文案...")
        context = await generate_marketing_copy(context, style=CopyStyle.natural)
        if context.messages:
            last_message = context.messages[-1]
            print(f"  ✓ 生成的文案: {last_message['content']}")
        
        print("\n" + "=" * 80)
        print("完整流程测试成功！")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ 集成测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


async def main():
    """Run all tests."""
    await test_product_tool()
    await test_behavior_tool()
    await test_rag_tool()
    await test_copy_tool()
    await test_integration()
    
    print("\n" + "=" * 80)
    print("所有测试完成！")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())


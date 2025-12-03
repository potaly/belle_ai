"""测试从数据库初始化向量存储"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.db.init_vector_store import load_products_from_db, chunk_product_texts, main

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_load_products():
    """测试从数据库加载商品"""
    print("\n" + "=" * 60)
    print("测试: 从数据库加载商品数据")
    print("=" * 60)
    
    try:
        product_data = load_products_from_db()
        
        if not product_data:
            print("\n✗ 数据库中没有商品数据")
            print("  请先执行 sql/seed_data.sql 导入测试数据")
            return False
        
        print(f"\n✓ 成功加载 {len(product_data)} 个商品")
        print("\n前 3 个商品示例:")
        for i, product in enumerate(product_data[:3], 1):
            print(f"\n  {i}. SKU: {product['sku']}")
            print(f"     名称: {product['name']}")
            print(f"     文本长度: {len(product['text'])} 字符")
            print(f"     文本预览: {product['text'][:100]}...")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 加载商品数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_chunk_products():
    """测试商品文本分块"""
    print("\n" + "=" * 60)
    print("测试: 商品文本分块")
    print("=" * 60)
    
    try:
        product_data = load_products_from_db()
        
        if not product_data:
            print("✗ 没有商品数据，跳过测试")
            return False
        
        print(f"\n正在对 {len(product_data)} 个商品进行分块...")
        chunks = chunk_product_texts(product_data, chunk_size=300, overlap=50)
        
        print(f"\n✓ 成功生成 {len(chunks)} 个文本块")
        print(f"  - 平均每个商品: {len(chunks) / len(product_data):.1f} 个块")
        
        print("\n前 3 个文本块示例:")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"\n  {i}. 长度: {len(chunk)} 字符")
            print(f"     内容: {chunk[:150]}...")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 文本分块失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 60)
    print("数据库向量存储初始化测试")
    print("=" * 60)
    
    print("\n注意: 此测试会检查数据库连接和商品数据")
    print("如果测试通过，可以运行以下命令初始化向量存储:")
    print("  python app/db/init_vector_store.py")
    
    results = []
    
    # 测试 1: 加载商品
    results.append(("加载商品数据", test_load_products()))
    
    # 测试 2: 文本分块
    if results[0][1]:  # 如果加载成功
        results.append(("文本分块", test_chunk_products()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✓ 所有测试通过！可以运行初始化脚本:")
        print("  python app/db/init_vector_store.py")
    else:
        print("\n⚠ 部分测试失败，请检查:")
        print("  1. 数据库连接配置是否正确")
        print("  2. 是否已执行 sql/schema.sql 创建表结构")
        print("  3. 是否已执行 sql/seed_data.sql 导入测试数据")
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)


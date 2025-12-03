"""测试嵌入模型和向量存储功能"""
from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.config import get_settings
from app.services.embedding_client import get_embedding_client
from app.services.vector_store import VectorStore

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_embedding_client():
    """测试嵌入客户端"""
    print("\n" + "=" * 60)
    print("测试 1: 嵌入向量生成")
    print("=" * 60)
    
    client = get_embedding_client()
    settings = get_settings()
    
    print(f"\n配置信息:")
    print(f"  - API Key: {'已配置' if client.api_key else '未配置'}")
    print(f"  - Base URL: {client.base_url or '未配置'}")
    print(f"  - Model: {client.model}")
    
    # 测试文本
    test_texts = [
        "这是一双舒适的运动鞋，适合日常跑步和健身",
        "时尚高跟鞋，优雅设计，适合正式场合",
        "百搭小白鞋，简约风格，适合多种穿搭"
    ]
    
    print(f"\n测试文本 ({len(test_texts)} 条):")
    for i, text in enumerate(test_texts, 1):
        print(f"  {i}. {text}")
    
    try:
        print("\n正在生成嵌入向量...")
        embeddings = await client.embed_texts(test_texts)
        
        if embeddings:
            print(f"\n✓ 成功生成 {len(embeddings)} 个嵌入向量")
            print(f"  - 向量维度: {len(embeddings[0])}")
            print(f"  - 向量示例 (前10维): {embeddings[0][:10]}")
            
            # 检查向量是否归一化
            import numpy as np
            norm = np.linalg.norm(embeddings[0])
            print(f"  - 向量范数: {norm:.6f} (应该接近 1.0，表示已归一化)")
            
            return True
        else:
            print("\n✗ 未生成嵌入向量")
            return False
            
    except Exception as e:
        print(f"\n✗ 生成嵌入向量失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_store_build():
    """测试向量存储构建"""
    print("\n" + "=" * 60)
    print("测试 2: 向量存储构建")
    print("=" * 60)
    
    # 测试文本块
    test_chunks = [
        "商品名称：运动鞋女2024新款时尚。商品SKU：8WZ01CM1。商品描述：这是一双专为女性设计的运动鞋，采用真皮材质，黑色经典配色，适合四季穿着，适合运动场景。商品标签：百搭、舒适、时尚。商品属性：color：黑色，material：真皮，scene：运动，season：四季。商品价格：458.00元",
        "商品名称：小白鞋女2023新款经典。商品SKU：8WZ02CM2。商品描述：经典小白鞋设计，帆布材质，白色清新配色，适合春秋季节，适合休闲场景。商品标签：百搭、轻便、透气。商品属性：color：白色，material：帆布，scene：休闲，season：春秋。商品价格：328.00元",
        "商品名称：高跟鞋女2024新款优雅。商品SKU：8WZ03CM3。商品描述：优雅高跟鞋设计，真皮材质，黑色经典配色，适合四季穿着，适合约会场景。商品标签：时尚、增高、优雅。商品属性：color：黑色，material：真皮，scene：约会，season：四季。商品价格：688.00元",
    ]
    
    print(f"\n测试文本块 ({len(test_chunks)} 个):")
    for i, chunk in enumerate(test_chunks, 1):
        print(f"  {i}. {chunk[:80]}...")
    
    try:
        print("\n正在构建向量索引...")
        vector_store = VectorStore(index_path="./test_vector_store/faiss.index")
        vector_store.build_index(test_chunks)
        
        print("\n正在保存索引...")
        vector_store.save()
        
        stats = vector_store.get_stats()
        print(f"\n✓ 索引构建成功")
        print(f"  - 向量数量: {stats['num_vectors']}")
        print(f"  - 向量维度: {stats['dimension']}")
        print(f"  - 文本块数量: {stats['num_chunks']}")
        print(f"  - 索引路径: {vector_store.index_path}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 索引构建失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_vector_store_search():
    """测试向量存储搜索"""
    print("\n" + "=" * 60)
    print("测试 3: 向量存储搜索")
    print("=" * 60)
    
    try:
        print("\n正在加载索引...")
        vector_store = VectorStore(index_path="./test_vector_store/faiss.index")
        
        if not vector_store.load():
            print("✗ 索引文件不存在，请先运行测试 2")
            return False
        
        print("✓ 索引加载成功")
        
        # 测试查询
        test_queries = [
            "舒适的运动鞋",
            "时尚的高跟鞋",
            "百搭的小白鞋"
        ]
        
        for query in test_queries:
            print(f"\n查询: '{query}'")
            results = vector_store.search(query, top_k=2)
            
            if results:
                print(f"  找到 {len(results)} 个结果:")
                for i, (chunk, score) in enumerate(results, 1):
                    print(f"    {i}. 相似度: {score:.4f} (越小越相似)")
                    print(f"       内容: {chunk[:100]}...")
            else:
                print("  未找到结果")
        
        return True
        
    except Exception as e:
        print(f"\n✗ 搜索测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_config():
    """测试配置"""
    print("\n" + "=" * 60)
    print("测试 0: 配置检查")
    print("=" * 60)
    
    settings = get_settings()
    
    print("\n当前配置:")
    print(f"  - LLM API Key: {'已配置' if settings.llm_api_key else '未配置'}")
    print(f"  - LLM Base URL: {settings.llm_base_url or '未配置'}")
    print(f"  - LLM Model: {settings.llm_model}")
    print(f"  - Embedding API Key: {getattr(settings, 'embedding_api_key', None) or '未配置（将使用 LLM API Key）'}")
    print(f"  - Embedding Base URL: {getattr(settings, 'embedding_base_url', None) or '未配置（将使用 LLM Base URL）'}")
    print(f"  - Embedding Model: {getattr(settings, 'embedding_model', 'text-embedding-v2')}")
    
    # 检查配置建议
    print("\n配置建议:")
    if not settings.llm_api_key:
        print("  ⚠ 未配置 LLM_API_KEY，将使用 stub 嵌入（仅用于测试）")
    elif not settings.llm_base_url:
        print("  ⚠ 未配置 LLM_BASE_URL，将使用 stub 嵌入（仅用于测试）")
    else:
        print("  ✓ 配置完整，将使用真实的嵌入 API")
    
    return True


async def main():
    """主测试函数"""
    print("=" * 60)
    print("嵌入模型和向量存储功能测试")
    print("=" * 60)
    
    results = []
    
    # 测试 0: 配置检查
    results.append(("配置检查", test_config()))
    
    # 测试 1: 嵌入向量生成
    results.append(("嵌入向量生成", await test_embedding_client()))
    
    # 测试 2: 向量存储构建
    results.append(("向量存储构建", test_vector_store_build()))
    
    # 测试 3: 向量存储搜索
    results.append(("向量存储搜索", test_vector_store_search()))
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n🎉 所有测试通过！")
    else:
        print("\n⚠ 部分测试失败，请检查配置和日志")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)


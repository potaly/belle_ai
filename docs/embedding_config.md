# 阿里百炼嵌入模型配置指南

## 概述

本项目已集成阿里百炼平台的嵌入模型，用于 V2 版本的 RAG（检索增强生成）功能。

## 支持的模型

### text-embedding-v2（推荐）

- **模型名称**: `text-embedding-v2`
- **特点**:
  - 阿里百炼平台默认的文本嵌入模型
  - 支持中英文双语以及多种其他语言
  - 向量结果已进行归一化处理
  - 适合中文场景的文本检索和相似度计算
- **向量维度**: 自动检测（通常为 1536 维）
- **适用场景**: 
  - 商品描述检索
  - 语义相似度搜索
  - RAG 知识库构建

## 配置方法

### 方式一：使用 LLM 配置（推荐）

如果您的 LLM 和嵌入模型都使用阿里百炼平台，可以复用 LLM 配置：

```env
# .env 文件
LLM_API_KEY=sk-your-api-key-here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max

# 嵌入模型会自动使用 LLM 配置，并自动转换为嵌入端点
# 默认模型: text-embedding-v2
```

系统会自动将 `LLM_BASE_URL` 转换为嵌入端点：
- `https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions`
- → `https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings`

### 方式二：独立配置嵌入模型

如果需要使用不同的 API Key 或端点，可以单独配置：

```env
# .env 文件
# LLM 配置
LLM_API_KEY=sk-your-llm-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max

# 嵌入模型配置（可选，会回退到 LLM 配置）
EMBEDDING_API_KEY=sk-your-embedding-api-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
EMBEDDING_MODEL=text-embedding-v2
```

## API 端点格式

阿里百炼平台使用 OpenAI 兼容的 API 格式：

### 请求格式

```json
POST https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
Headers:
  Authorization: Bearer sk-your-api-key
  Content-Type: application/json

Body:
{
  "model": "text-embedding-v2",
  "input": ["文本1", "文本2", ...]
}
```

### 响应格式

```json
{
  "data": [
    {
      "embedding": [0.1, 0.2, ...],
      "index": 0
    },
    ...
  ],
  "model": "text-embedding-v2",
  "usage": {
    "prompt_tokens": 10,
    "total_tokens": 10
  }
}
```

## 使用示例

### 1. 初始化向量存储

```bash
# 从 MySQL 加载商品数据并构建索引
python app/db/init_vector_store.py
```

### 2. 在代码中使用

```python
from app.services.vector_store import VectorStore

# 加载索引
vector_store = VectorStore()
vector_store.load()

# 搜索相似商品
results = vector_store.search("舒适的运动鞋", top_k=5)
for chunk, score in results:
    print(f"相似度: {score:.4f}")
    print(f"内容: {chunk[:100]}...")
```

### 3. 直接使用嵌入客户端

```python
from app.services.embedding_client import get_embedding_client
import asyncio

client = get_embedding_client()
texts = ["这是一双舒适的运动鞋", "这是一双时尚的高跟鞋"]
embeddings = asyncio.run(client.embed_texts(texts))
print(f"生成了 {len(embeddings)} 个嵌入向量")
print(f"向量维度: {len(embeddings[0])}")
```

## 技术细节

### 向量归一化

- 阿里百炼的 `text-embedding-v2` 模型返回的向量已经归一化
- 在 FAISS 索引中，我们再次进行 L2 归一化以确保一致性
- 使用 L2（欧氏距离）进行相似度计算

### 错误处理

- 自动重试机制：API 调用失败时自动重试 2 次
- 降级策略：如果 API 调用失败，会使用 stub 嵌入（基于 MD5 的伪嵌入）用于测试
- 详细日志：记录请求 URL、模型、文本数量、响应状态等信息

### 性能优化

- 批量处理：支持一次请求处理多个文本
- 异步调用：使用 `httpx.AsyncClient` 进行异步 HTTP 请求
- 超时设置：默认 30 秒超时，可根据网络情况调整

## 故障排查

### 问题 1: API 调用返回 401 错误

**原因**: API Key 无效或未配置

**解决**:
1. 检查 `.env` 文件中的 `LLM_API_KEY` 或 `EMBEDDING_API_KEY`
2. 确认 API Key 格式正确（通常以 `sk-` 开头）
3. 验证 API Key 在阿里百炼平台是否有效

### 问题 2: API 调用返回 404 错误

**原因**: API 端点 URL 不正确

**解决**:
1. 检查 `LLM_BASE_URL` 或 `EMBEDDING_BASE_URL` 配置
2. 确保端点格式为：`https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings`
3. 如果使用 LLM 配置，系统会自动转换，但需要确保 `LLM_BASE_URL` 格式正确

### 问题 3: 使用 stub 嵌入而非真实 API

**原因**: API 配置缺失或 API 调用失败

**解决**:
1. 检查日志中的警告信息
2. 确认 API Key 和 Base URL 已正确配置
3. 检查网络连接和防火墙设置
4. 查看详细日志了解具体错误原因

### 问题 4: 向量维度不匹配

**原因**: 不同模型返回的向量维度不同

**解决**:
1. 系统会自动检测向量维度
2. 如果使用不同的嵌入模型，确保重新构建索引
3. 检查 `EMBEDDING_MODEL` 配置是否正确

## 参考资源

- [阿里百炼平台文档](https://help.aliyun.com/zh/model-studio/)
- [DashScope API 文档](https://help.aliyun.com/zh/model-studio/developer-reference/api-details-9)
- [FAISS 文档](https://github.com/facebookresearch/faiss)

## 更新日志

- **2024-12-02**: 初始版本，支持阿里百炼 `text-embedding-v2` 模型
- 默认模型设置为 `text-embedding-v2`
- 优化 URL 自动转换逻辑
- 增强错误处理和日志记录


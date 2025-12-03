# V2 向量搜索功能 - 快速使用指南

## 功能概述

V2 版本新增了**向量语义搜索**功能，可以根据用户输入的文本，智能搜索相关的商品信息。

## 核心文件说明

### 1. 嵌入向量客户端 (`app/services/embedding_client.py`)

**用途**：调用阿里百炼 API，将文本转换为向量（1536 个数字）

**在哪里使用**：
- 构建索引时：将商品文本转换为向量
- 搜索时：将查询文本转换为向量

**关键代码**：
```python
from app.services.embedding_client import get_embedding_client
import asyncio

client = get_embedding_client()
embeddings = asyncio.run(client.embed_texts(["舒适的运动鞋"]))
# 返回: [[0.1, 0.2, ...]] (1536个数字)
```

---

### 2. 向量存储 (`app/services/vector_store.py`)

**用途**：使用 FAISS 构建向量索引，实现快速搜索

**在哪里使用**：
- 初始化时：构建索引并保存
- API 接口中：执行搜索

**关键代码**：
```python
from app.services.vector_store import VectorStore

# 构建索引
vector_store = VectorStore()
vector_store.build_index(chunks)
vector_store.save()

# 搜索
vector_store.load()
results = vector_store.search("舒适的运动鞋", top_k=5)
```

---

### 3. 文本分块工具 (`app/utils/chunk_utils.py`)

**用途**：将长文本分割成小块（300字符），便于向量化

**在哪里使用**：
- 初始化脚本中：对商品文本进行分块

**关键代码**：
```python
from app.utils.chunk_utils import chunk_text

chunks = chunk_text("很长的商品描述...", chunk_size=300, overlap=50)
```

---

### 4. 初始化脚本 (`app/db/init_vector_store.py`)

**用途**：从数据库加载商品，构建向量索引

**如何使用**：
```bash
python app/db/init_vector_store.py
```

**做了什么**：
1. 从 MySQL 加载所有商品
2. 将商品文本分块
3. 生成向量并构建索引
4. 保存到 `./vector_store/faiss.index`

---

### 5. API 接口 (`app/api/v1/vector_search.py`)

**用途**：提供 HTTP API，供外部调用搜索功能

**API 地址**：
- 搜索接口：`POST /ai/vector/search`
- 统计接口：`GET /ai/vector/stats`

**如何使用**：

```bash
# 使用 curl
curl -X POST "http://127.0.0.1:8000/ai/vector/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "舒适的运动鞋", "top_k": 5}'
```

```python
# 使用 Python
import requests

response = requests.post(
    "http://127.0.0.1:8000/ai/vector/search",
    json={"query": "舒适的运动鞋", "top_k": 5}
)
print(response.json())
```

---

## 完整使用流程

### 第一步：配置环境

在 `.env` 文件中配置：
```env
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
```

### 第二步：初始化索引

```bash
python app/db/init_vector_store.py
```

**输出**：
- `./vector_store/faiss.index` - 向量索引文件
- `./vector_store/chunks.pkl` - 文本块文件

### 第三步：启动服务

```bash
uvicorn app.main:app --reload
```

### 第四步：调用 API

```bash
curl -X POST "http://127.0.0.1:8000/ai/vector/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "舒适的运动鞋", "top_k": 5}'
```

---

## API 接口详细说明

### 搜索接口

**地址**：`POST /ai/vector/search`

**请求**：
```json
{
  "query": "舒适的运动鞋",
  "top_k": 5
}
```

**响应**：
```json
{
  "code": 200,
  "message": "搜索成功",
  "data": {
    "query": "舒适的运动鞋",
    "total": 5,
    "results": [
      {
        "rank": 1,
        "score": 0.8769,
        "chunk": "[商品：运动鞋女2024新款时尚（SKU：8WZ01CM1）] 商品名称：运动鞋女2024新款时尚..."
      }
    ]
  }
}
```

**参数说明**：
- `query`: 搜索查询文本（必填）
- `top_k`: 返回结果数量，1-20，默认5

**响应说明**：
- `score`: 相似度分数，越小越相似
- `chunk`: 匹配的商品文本块

### 统计接口

**地址**：`GET /ai/vector/stats`

**响应**：
```json
{
  "code": 200,
  "data": {
    "loaded": true,
    "num_vectors": 150,
    "dimension": 1536,
    "num_chunks": 150
  }
}
```

---

## 代码调用关系图

```
用户请求
    ↓
API 接口 (vector_search.py)
    ↓
向量存储 (vector_store.py)
    ↓
嵌入客户端 (embedding_client.py)
    ↓
阿里百炼 API
```

---

## 常见问题

### Q: 在哪里使用这些代码？

**A**: 
- **初始化**：运行 `python app/db/init_vector_store.py`
- **API 调用**：通过 HTTP 请求 `/ai/vector/search`
- **代码集成**：导入 `VectorStore` 类使用

### Q: 如何更新索引？

**A**: 
1. 更新 MySQL 商品数据
2. 重新运行初始化脚本
3. 重启服务

### Q: 索引文件在哪里？

**A**: 
- `./vector_store/faiss.index`
- `./vector_store/chunks.pkl`

---

## 相关文档

- `docs/v2_code_explanation.md` - 详细代码说明
- `docs/vector_search_api.md` - API 接口文档
- `docs/embedding_config.md` - 嵌入模型配置


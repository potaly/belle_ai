# RAG 调试端点文档

## 概述

RAG 调试端点用于预览和测试 RAG（检索增强生成）的检索结果，帮助开发者调试和优化检索效果。

## 端点信息

- **URL**: `POST /admin/rag/preview`
- **访问限制**: 仅在 `DEBUG=true` 时可用
- **标签**: `admin`, `rag-debug`

## 启用调试模式

在 `.env` 文件中设置：

```bash
DEBUG=true
```

或者在环境变量中设置：

```bash
export DEBUG=true
```

## 请求格式

### 请求体

```json
{
  "query": "小白鞋 软底",
  "top_k": 5
}
```

### 字段说明

- `query` (string, 必需): 搜索查询文本，最少 1 个字符
- `top_k` (int, 可选): 返回的结果数量，默认 5，范围 1-20

## 响应格式

### 成功响应 (200)

```json
{
  "success": true,
  "message": "RAG preview completed successfully",
  "data": {
    "query": "小白鞋 软底",
    "top_k": 5,
    "results": [
      {
        "chunk": "这是一款白色的舒适跑鞋，具有软底、轻便的特点...",
        "score": 1.8923,
        "rank": 1
      },
      {
        "chunk": "这是一款米色的休闲鞋，具有舒适、透气、轻便的特点...",
        "score": 1.9056,
        "rank": 2
      }
    ],
    "statistics": {
      "total_results": 5,
      "min_score": 1.8923,
      "max_score": 1.9521,
      "avg_score": 1.9234
    }
  }
}
```

### 字段说明

- `results`: 检索到的文本块列表
  - `chunk`: 文本块内容
  - `score`: 相似度分数（L2 距离，越小越相似）
  - `rank`: 排名（从 1 开始）
- `statistics`: 统计信息
  - `total_results`: 结果总数
  - `min_score`: 最小分数（最相似）
  - `max_score`: 最大分数（最不相似）
  - `avg_score`: 平均分数

## 错误响应

### 403 Forbidden - 调试模式未启用

```json
{
  "detail": "Debug endpoints are only available when DEBUG=true in environment variables"
}
```

### 503 Service Unavailable - 向量存储未加载

```json
{
  "detail": "Vector store is not loaded. Run 'python app/db/init_vector_store.py' to initialize."
}
```

### 500 Internal Server Error - 服务器错误

```json
{
  "detail": "Failed to preview RAG results: <error message>"
}
```

## 使用示例

### cURL

```bash
# 设置 DEBUG 模式
export DEBUG=true

# 调用端点
curl -X POST "http://127.0.0.1:8000/admin/rag/preview" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "小白鞋 软底",
    "top_k": 5
  }'
```

### Python

```python
import requests

# 确保 DEBUG=true 在环境变量中
response = requests.post(
    "http://127.0.0.1:8000/admin/rag/preview",
    json={
        "query": "小白鞋 软底",
        "top_k": 5
    }
)

if response.status_code == 200:
    data = response.json()
    print(f"查询: {data['data']['query']}")
    print(f"结果数: {data['data']['statistics']['total_results']}")
    for result in data['data']['results']:
        print(f"Rank {result['rank']}: Score={result['score']:.4f}")
        print(f"  {result['chunk'][:100]}...")
else:
    print(f"错误: {response.status_code} - {response.text}")
```

## 注意事项

1. **安全性**: 此端点仅在调试模式下可用，生产环境应确保 `DEBUG=false`
2. **性能**: 每次调用都会执行向量搜索，可能较慢
3. **向量存储**: 需要先运行 `python app/db/init_vector_store.py` 初始化向量索引
4. **分数说明**: 
   - 使用 L2 欧氏距离
   - 归一化后的向量，距离范围是 0-2
   - 距离越小表示越相似（< 1.0 表示高度相似）

## 相关文件

- `app/api/v1/rag_debug.py` - 端点实现
- `app/services/rag_service.py` - RAG 服务
- `app/services/vector_store.py` - 向量存储
- `app/core/config.py` - 配置管理


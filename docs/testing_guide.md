# 测试指南

本文档介绍如何测试嵌入模型和向量存储功能。

## 测试前准备

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

确保安装了以下关键依赖：
- `faiss-cpu` - FAISS 向量数据库
- `numpy` - 数值计算
- `httpx` - HTTP 客户端

### 2. 配置环境变量

在 `.env` 文件中配置阿里百炼 API（至少需要 LLM 配置）：

```env
# 方式一：复用 LLM 配置（推荐）
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max

# 方式二：独立配置嵌入模型（可选）
EMBEDDING_API_KEY=sk-your-embedding-key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
EMBEDDING_MODEL=text-embedding-v2
```

### 3. 准备数据库（可选，用于完整测试）

如果测试从数据库初始化向量存储，需要：

1. 创建数据库表：
```bash
mysql -u root -p < sql/schema.sql
```

2. 导入测试数据：
```bash
mysql -u root -p < sql/seed_data.sql
```

## 测试步骤

### 测试 1: 基础功能测试（推荐先运行）

测试嵌入模型和向量存储的基本功能，不需要数据库。

```bash
python test_embedding.py
```

**测试内容**：
1. ✅ 配置检查 - 验证环境变量配置
2. ✅ 嵌入向量生成 - 测试文本嵌入生成
3. ✅ 向量存储构建 - 测试 FAISS 索引构建
4. ✅ 向量存储搜索 - 测试语义搜索功能

**预期输出**：
```
============================================================
嵌入模型和向量存储功能测试
============================================================

============================================================
测试 0: 配置检查
============================================================
当前配置:
  - LLM API Key: 已配置
  - LLM Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
  - Embedding Model: text-embedding-v2
  ...
✓ 成功生成 3 个嵌入向量
  - 向量维度: 1536
  ...
```

**如果看到 "using stub embeddings" 警告**：
- 说明 API 配置有问题，会使用伪嵌入进行测试
- 检查 `.env` 文件中的 API Key 和 Base URL
- 参考 `docs/embedding_config.md` 进行配置

### 测试 2: 数据库初始化测试

测试从 MySQL 数据库加载商品数据并初始化向量存储。

```bash
python test_init_vector_store.py
```

**测试内容**：
1. ✅ 加载商品数据 - 从数据库查询商品
2. ✅ 文本分块 - 将商品文本分块处理

**预期输出**：
```
============================================================
数据库向量存储初始化测试
============================================================

✓ 成功加载 100 个商品
✓ 成功生成 150 个文本块
```

**如果测试失败**：
- 检查数据库连接配置（`DATABASE_URL`）
- 确认已执行 `sql/schema.sql` 创建表
- 确认已执行 `sql/seed_data.sql` 导入数据

### 测试 3: 完整初始化流程

如果测试 2 通过，可以运行完整的初始化脚本：

```bash
python app/db/init_vector_store.py
```

**功能**：
1. 从 MySQL 加载所有商品数据
2. 将商品文本分块（300 字符，重叠 50）
3. 生成嵌入向量（调用阿里百炼 API）
4. 构建 FAISS 索引
5. 保存索引到 `./vector_store/faiss.index`

**预期输出**：
```
============================================================
Vector Store Initialization
============================================================

[Step 1] Loading products from MySQL...
[INIT] Loaded 100 products from database
[INIT] Prepared 100 product texts

[Step 2] Chunking product texts...
[INIT] Chunked 100 products into 150 chunks

[Step 3] Building FAISS index...
[EMBEDDING] Calling API: ...
[VECTOR_STORE] ✓ Index built: 150 vectors, dim=1536

[Step 4] Saving index to disk...
[VECTOR_STORE] Saved index to ./vector_store/faiss.index

============================================================
Initialization Complete!
============================================================
Index Statistics:
  - Vectors: 150
  - Dimension: 1536
  - Chunks: 150
```

## 测试场景

### 场景 1: 仅测试嵌入 API（不构建索引）

```python
from app.services.embedding_client import get_embedding_client
import asyncio

client = get_embedding_client()
texts = ["这是一双舒适的运动鞋", "这是一双时尚的高跟鞋"]
embeddings = asyncio.run(client.embed_texts(texts))
print(f"生成了 {len(embeddings)} 个嵌入向量")
print(f"向量维度: {len(embeddings[0])}")
```

### 场景 2: 测试向量搜索

```python
from app.services.vector_store import VectorStore

# 加载索引
vector_store = VectorStore()
if vector_store.load():
    # 搜索相似商品
    results = vector_store.search("舒适的运动鞋", top_k=5)
    for chunk, score in results:
        print(f"相似度: {score:.4f}")
        print(f"内容: {chunk[:100]}...")
else:
    print("索引未找到，请先运行初始化脚本")
```

### 场景 3: 验证配置

```python
from app.core.config import get_settings

settings = get_settings()
print(f"LLM API Key: {'已配置' if settings.llm_api_key else '未配置'}")
print(f"LLM Base URL: {settings.llm_base_url}")
print(f"Embedding Model: {getattr(settings, 'embedding_model', 'text-embedding-v2')}")
```

## 常见问题

### Q1: 测试时显示 "using stub embeddings"

**原因**: API 配置缺失或无效

**解决**:
1. 检查 `.env` 文件是否存在
2. 确认 `LLM_API_KEY` 和 `LLM_BASE_URL` 已配置
3. 验证 API Key 是否有效
4. 检查网络连接

### Q2: 测试时显示 "Index files not found"

**原因**: 尚未构建向量索引

**解决**:
1. 先运行 `python test_embedding.py` 构建测试索引
2. 或运行 `python app/db/init_vector_store.py` 构建完整索引

### Q3: 数据库连接失败

**原因**: 数据库配置错误或数据库未启动

**解决**:
1. 检查 `DATABASE_URL` 配置
2. 确认 MySQL 服务已启动
3. 验证数据库用户名和密码
4. 确认数据库 `belle_ai` 已创建

### Q4: 嵌入 API 调用超时

**原因**: 网络问题或 API 服务异常

**解决**:
1. 检查网络连接
2. 增加超时时间（在 `embedding_client.py` 中修改）
3. 检查阿里百炼平台服务状态

### Q5: 向量维度不匹配

**原因**: 使用了不同的嵌入模型

**解决**:
1. 确保使用相同的嵌入模型（`text-embedding-v2`）
2. 如果更换模型，需要重新构建索引
3. 检查 `EMBEDDING_MODEL` 配置

## 性能测试

### 测试嵌入生成速度

```python
import asyncio
import time
from app.services.embedding_client import get_embedding_client

client = get_embedding_client()
texts = ["测试文本"] * 10  # 10 个文本

start = time.time()
embeddings = asyncio.run(client.embed_texts(texts))
duration = time.time() - start

print(f"生成了 {len(embeddings)} 个嵌入向量")
print(f"耗时: {duration:.2f} 秒")
print(f"平均: {duration/len(texts)*1000:.2f} 毫秒/文本")
```

### 测试搜索速度

```python
import time
from app.services.vector_store import VectorStore

vector_store = VectorStore()
vector_store.load()

query = "舒适的运动鞋"
start = time.time()
results = vector_store.search(query, top_k=10)
duration = time.time() - start

print(f"搜索耗时: {duration*1000:.2f} 毫秒")
print(f"找到 {len(results)} 个结果")
```

## 下一步

测试通过后，可以：

1. **集成到 API**: 在 FastAPI 接口中使用向量存储
2. **优化性能**: 根据实际数据量调整分块大小和索引类型
3. **扩展功能**: 添加更多搜索功能和过滤条件

参考文档：
- `docs/embedding_config.md` - 嵌入模型配置指南
- `README.md` - 项目总体说明


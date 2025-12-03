# V2 版本代码详细说明

本文档详细说明 V2 版本（RAG 向量搜索）的代码结构、用途和使用方法。

## 目录结构

```
app/
├── services/
│   ├── embedding_client.py      # 嵌入向量客户端（调用阿里百炼API）
│   └── vector_store.py           # FAISS向量存储（索引构建和搜索）
├── utils/
│   └── chunk_utils.py           # 文本分块工具（将长文本分割成小块）
├── db/
│   └── init_vector_store.py     # 初始化脚本（从数据库构建索引）
└── api/v1/
    └── vector_search.py         # API接口（对外提供搜索服务）
```

## 核心模块说明

### 1. embedding_client.py - 嵌入向量客户端

**文件位置**: `app/services/embedding_client.py`

**功能说明**：
- 调用阿里百炼平台的嵌入模型 API，将文本转换为向量
- 支持批量处理多个文本
- 自动处理错误和重试
- 如果 API 配置缺失，使用 stub 嵌入（用于测试）

**主要类和方法**：

```python
class EmbeddingClient:
    """嵌入向量客户端"""
    
    async def embed_texts(texts: List[str]) -> List[List[float]]:
        """
        将文本列表转换为向量列表
        
        参数：
        - texts: 文本列表，例如 ["舒适的运动鞋", "时尚的高跟鞋"]
        
        返回：
        - 向量列表，每个向量是 1536 个浮点数
        
        使用位置：
        - vector_store.py: 构建索引时生成向量
        - vector_store.py: 搜索时生成查询向量
        """
```

**使用示例**：
```python
from app.services.embedding_client import get_embedding_client
import asyncio

client = get_embedding_client()
texts = ["舒适的运动鞋", "时尚的高跟鞋"]
embeddings = asyncio.run(client.embed_texts(texts))
# embeddings 是一个列表，包含 2 个向量，每个向量有 1536 个数字
```

**配置要求**：
- 需要在 `.env` 文件中配置 `LLM_API_KEY` 和 `LLM_BASE_URL`
- 或者单独配置 `EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL`

---

### 2. vector_store.py - 向量存储

**文件位置**: `app/services/vector_store.py`

**功能说明**：
- 使用 FAISS 构建向量索引，实现快速相似度搜索
- 支持索引的保存和加载
- 提供语义搜索功能

**主要类和方法**：

```python
class VectorStore:
    """FAISS 向量存储"""
    
    def build_index(chunks: List[str]) -> None:
        """
        构建向量索引
        
        功能：
        1. 将文本块转换为向量（调用 embedding_client）
        2. 使用 FAISS 构建索引
        3. 保存索引到磁盘
        
        参数：
        - chunks: 文本块列表
        
        使用位置：
        - app/db/init_vector_store.py: 初始化时构建索引
        """
    
    def search(query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        搜索相似文本
        
        功能：
        1. 将查询文本转换为向量
        2. 在索引中搜索最相似的向量
        3. 返回相似度最高的 top_k 个结果
        
        参数：
        - query: 查询文本，例如 "舒适的运动鞋"
        - top_k: 返回结果数量，默认 5
        
        返回：
        - 结果列表，每个元素是 (文本块, 相似度分数) 的元组
        
        使用位置：
        - app/api/v1/vector_search.py: API 接口中调用
        """
    
    def save() -> None:
        """
        保存索引到磁盘
        
        保存内容：
        - FAISS 索引文件: ./vector_store/faiss.index
        - 文本块元数据: ./vector_store/chunks.pkl
        """
    
    def load() -> bool:
        """
        从磁盘加载索引
        
        返回：
        - True: 加载成功
        - False: 文件不存在或加载失败
        """
```

**使用示例**：
```python
from app.services.vector_store import VectorStore

# 构建索引
vector_store = VectorStore()
chunks = ["商品1的描述...", "商品2的描述..."]
vector_store.build_index(chunks)
vector_store.save()

# 搜索
vector_store.load()
results = vector_store.search("舒适的运动鞋", top_k=5)
for chunk, score in results:
    print(f"相似度: {score}, 内容: {chunk[:100]}...")
```

---

### 3. chunk_utils.py - 文本分块工具

**文件位置**: `app/utils/chunk_utils.py`

**功能说明**：
- 将长文本分割成较小的文本块
- 支持重叠分块，确保上下文不丢失
- 智能分割：在标点符号处分割，避免截断单词

**主要函数**：

```python
def chunk_text(text: str, chunk_size: int = 300, overlap: int = 50) -> List[str]:
    """
    将单个文本分割成多个文本块
    
    参数：
    - text: 要分割的文本
    - chunk_size: 每个块的大小（字符数），默认 300
    - overlap: 相邻块之间的重叠字符数，默认 50
    
    返回：
    - 文本块列表
    
    使用位置：
    - app/db/init_vector_store.py: 对商品文本进行分块
    """
```

**使用示例**：
```python
from app.utils.chunk_utils import chunk_text

text = "这是一段很长的商品描述，包含了很多信息..."
chunks = chunk_text(text, chunk_size=300, overlap=50)
# 返回: ["这是第一块...", "第二块（与前一块重叠50字符）...", ...]
```

**为什么需要分块**：
1. 嵌入模型有长度限制，长文本需要分割
2. 分块后可以更精确地匹配相关部分
3. 重叠确保上下文信息不丢失

---

### 4. init_vector_store.py - 初始化脚本

**文件位置**: `app/db/init_vector_store.py`

**功能说明**：
- 从 MySQL 数据库加载商品数据
- 将商品文本分块
- 构建向量索引并保存

**主要函数**：

```python
def load_products_from_db() -> list[dict]:
    """
    从数据库加载商品数据
    
    返回：
    - 商品数据列表，每个元素包含 sku, name, text
    """
    
def chunk_product_texts(product_data: list[dict]) -> list[str]:
    """
    将商品文本分块
    
    参数：
    - product_data: 商品数据列表
    
    返回：
    - 文本块列表
    """
    
def main():
    """
    主函数：执行完整的初始化流程
    1. 加载商品数据
    2. 文本分块
    3. 构建索引
    4. 保存索引
    """
```

**使用方法**：
```bash
# 确保数据库中有商品数据
python app/db/init_vector_store.py
```

**输出**：
- 索引文件: `./vector_store/faiss.index`
- 文本块文件: `./vector_store/chunks.pkl`

---

### 5. vector_search.py - API 接口

**文件位置**: `app/api/v1/vector_search.py`

**功能说明**：
- 提供 HTTP API 接口，供外部调用向量搜索功能
- 处理请求参数验证
- 调用向量存储进行搜索
- 返回格式化的搜索结果

**主要接口**：

```python
@router.post("/ai/vector/search")
async def vector_search(request: VectorSearchRequest):
    """
    向量搜索接口
    
    功能：
    1. 接收用户查询文本
    2. 调用 vector_store.search() 进行搜索
    3. 返回格式化的搜索结果
    
    请求：
    - query: 查询文本
    - top_k: 返回结果数量
    
    响应：
    - query: 原始查询
    - results: 搜索结果列表
    - total: 结果总数
    """
```

**API 地址**：
- 搜索接口: `POST http://127.0.0.1:8000/ai/vector/search`
- 统计接口: `GET http://127.0.0.1:8000/ai/vector/stats`

**使用示例**：
```bash
# 使用 curl
curl -X POST "http://127.0.0.1:8000/ai/vector/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "舒适的运动鞋", "top_k": 5}'

# 使用 Python
import requests
response = requests.post(
    "http://127.0.0.1:8000/ai/vector/search",
    json={"query": "舒适的运动鞋", "top_k": 5}
)
results = response.json()
```

---

## 完整工作流程

### 1. 初始化阶段（一次性）

```
MySQL 数据库
    ↓
init_vector_store.py
    ↓
加载商品数据
    ↓
chunk_utils.py (文本分块)
    ↓
embedding_client.py (生成向量)
    ↓
vector_store.py (构建索引)
    ↓
保存到磁盘 (faiss.index, chunks.pkl)
```

### 2. 搜索阶段（每次请求）

```
用户请求
    ↓
vector_search.py (API接口)
    ↓
embedding_client.py (生成查询向量)
    ↓
vector_store.py (向量搜索)
    ↓
返回搜索结果
```

## 代码调用关系

```
API 接口 (vector_search.py)
    ↓
向量存储 (vector_store.py)
    ↓
嵌入客户端 (embedding_client.py)
    ↓
阿里百炼 API
```

```
初始化脚本 (init_vector_store.py)
    ↓
文本分块 (chunk_utils.py)
    ↓
向量存储 (vector_store.py)
    ↓
嵌入客户端 (embedding_client.py)
```

## 配置文件说明

### .env 文件配置

```env
# LLM 配置（嵌入模型会复用）
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max

# 嵌入模型配置（可选，会回退到 LLM 配置）
EMBEDDING_MODEL=text-embedding-v2
```

### app/core/config.py

```python
class Settings:
    # 嵌入模型配置
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-v2"
```

## 使用步骤

### 步骤 1: 安装依赖

```bash
pip install -r requirements.txt
```

### 步骤 2: 配置环境变量

编辑 `.env` 文件，配置 API Key 和 Base URL

### 步骤 3: 初始化向量索引

```bash
python app/db/init_vector_store.py
```

### 步骤 4: 启动服务

```bash
uvicorn app.main:app --reload
```

### 步骤 5: 调用 API

```bash
curl -X POST "http://127.0.0.1:8000/ai/vector/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "舒适的运动鞋", "top_k": 5}'
```

## 常见问题

### Q1: 在哪里使用这些代码？

**回答**：
- **初始化**：运行 `python app/db/init_vector_store.py` 构建索引
- **API 调用**：通过 HTTP 请求调用 `/ai/vector/search` 接口
- **代码集成**：在其他 Python 代码中导入 `VectorStore` 类使用

### Q2: 如何更新索引？

**回答**：
1. 更新 MySQL 中的商品数据
2. 重新运行初始化脚本
3. 重启服务（索引会自动重新加载）

### Q3: 索引文件在哪里？

**回答**：
- 索引文件: `./vector_store/faiss.index`
- 文本块文件: `./vector_store/chunks.pkl`

### Q4: 如何测试功能？

**回答**：
```bash
# 基础功能测试
python test_embedding.py

# 数据库初始化测试
python test_init_vector_store.py
```

## 技术细节

### 向量维度
- 默认维度：1536（阿里百炼 text-embedding-v2）
- 自动检测：从 API 响应中获取实际维度

### 距离度量
- 使用 L2（欧氏距离）
- 分数越小表示越相似
- 所有向量在索引前进行 L2 归一化

### 索引类型
- 当前使用：`IndexFlatL2`（精确搜索）
- 适合规模：数万到数十万向量
- 可升级：大规模数据可使用 `IndexIVFFlat`（近似搜索）

## 相关文档

- `docs/embedding_config.md` - 嵌入模型配置指南
- `docs/vector_search_api.md` - API 接口详细文档
- `docs/testing_guide.md` - 测试指南

## 总结

V2 版本的代码实现了完整的 RAG（检索增强生成）功能：

1. **文本处理**：`chunk_utils.py` 将长文本分块
2. **向量生成**：`embedding_client.py` 调用阿里百炼 API 生成向量
3. **索引构建**：`vector_store.py` 使用 FAISS 构建向量索引
4. **搜索服务**：`vector_search.py` 提供 HTTP API 接口
5. **初始化工具**：`init_vector_store.py` 从数据库构建索引

所有模块都有详细的中文注释，方便理解和使用。


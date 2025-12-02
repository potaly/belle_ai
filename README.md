# AI Smart Guide Service

智能导购服务 - 为鞋类零售行业提供 AI 驱动的销售助手服务

## 项目概述

AI Smart Guide Service 是一个基于 FastAPI 的智能导购服务，专为微信小程序等前端应用提供 AI 能力。服务通过分析商品信息和用户行为，为导购人员生成朋友圈文案、分析商品卖点，帮助提升销售效率。

### 技术栈

- **Web 框架**: FastAPI (Python 3.10+)
- **ORM**: SQLAlchemy 2.0
- **数据库**: MySQL 8.0+
- **缓存**: Redis (可选，V2+)
- **向量数据库**: FAISS (V2+)
- **AI 模型**: 支持阿里百炼、DeepSeek、Qwen、OpenAI 等

---

## V1 功能特性

### 1. 商品文案生成 (`/ai/generate/copy`)
- **流式响应**: 使用 Server-Sent Events (SSE) 实时返回生成内容
- **低延迟**: 第一个 chunk 在 500ms 内发出
- **多风格支持**: 自然、专业、幽默三种文案风格
- **异步日志**: 自动记录 AI 任务日志到数据库

### 2. 商品分析 (`/ai/analyze/product`)
- **规则驱动**: 基于商品标签和属性智能分析
- **结构化输出**: 返回核心卖点、风格标签、适用场景、适合人群、解决痛点
- **自动推导**: 从 tags 和 attributes 自动推导分析结果

### 3. 数据管理
- **商品管理**: 支持商品信息存储和查询
- **行为日志**: 记录用户浏览、收藏等行为
- **AI 日志**: 记录所有 AI 调用任务，便于分析和优化

---

## 项目结构

```
belle-ai-service/
├── app/                          # 应用主目录
│   ├── main.py                  # FastAPI 应用入口
│   ├── core/                    # 核心配置
│   │   ├── config.py           # 配置管理（Pydantic BaseSettings）
│   │   └── database.py         # 数据库配置（SQLAlchemy 2.0）
│   ├── api/                     # API 路由
│   │   └── v1/                 # API v1 版本
│   │       ├── copy.py         # 文案生成接口
│   │       ├── product.py      # 商品分析接口
│   │       └── router.py       # 基础路由
│   ├── models/                  # ORM 模型
│   │   ├── product.py          # 商品模型
│   │   ├── guide.py            # 导购模型
│   │   ├── user_behavior_log.py # 用户行为日志模型
│   │   └── ai_task_log.py      # AI 任务日志模型
│   ├── schemas/                 # Pydantic 模型
│   │   ├── copy_schemas.py     # 文案生成请求/响应
│   │   └── product_schemas.py  # 商品分析请求/响应
│   ├── services/                # 业务逻辑层
│   │   ├── copy_service.py     # 文案生成服务
│   │   ├── product_service.py  # 商品分析服务
│   │   ├── streaming_generator.py # 流式生成器
│   │   ├── log_service.py      # 日志服务
│   │   └── llm_client.py       # LLM 客户端封装
│   └── repositories/             # 数据访问层
│       └── product_repository.py # 商品数据访问
├── sql/                          # SQL 脚本
│   ├── schema.sql               # 数据库表结构
│   └── seed_data.sql            # 种子数据
├── docs/                         # 文档
│   ├── PRD.md                   # 产品需求文档
│   ├── Architecture.md          # 架构文档
│   ├── product_analyze_api.md   # 商品分析接口文档
│   └── tags_query_explanation.md # Tags 查询说明
├── requirements.txt              # Python 依赖
├── .env.example                  # 环境变量示例
└── README.md                     # 项目说明（本文件）
```

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- MySQL 8.0+
- Redis (可选，V2+)

### 2. 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，配置数据库连接等信息。

### 4. 初始化数据库

#### 创建数据库

```sql
CREATE DATABASE belle_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

#### 导入表结构

```bash
mysql -u root -p belle_ai < sql/schema.sql
```

#### 导入种子数据

```bash
mysql -u root -p belle_ai < sql/seed_data.sql
```

或者使用 MySQL 客户端工具（如 Navicat、DBeaver）直接执行 SQL 文件。

### 5. 启动服务

```bash
# 使用 uvicorn 启动
uvicorn app.main:app --reload

# 或者指定主机和端口
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

服务启动后，访问以下地址：

- **API 文档**: http://127.0.0.1:8000/docs
- **健康检查**: http://127.0.0.1:8000/health
- **根端点**: http://127.0.0.1:8000/

---

## 接口说明

### 1. 商品文案生成接口 (`/ai/generate/copy`)

#### 功能说明

生成微信朋友圈文案，支持流式返回（SSE），第一个 chunk 在 500ms 内发出。

#### 请求示例

```bash
POST /ai/generate/copy
Content-Type: application/json

{
  "sku": "8WZ01CM1",
  "style": "natural"
}
```

#### 响应格式

使用 Server-Sent Events (SSE) 流式返回，格式如下：

```
data: {"type": "start", "total": 3, "style": "natural"}

data: {"type": "post_start", "index": 1, "total": 3}

data: {"type": "token", "content": "今天推荐这款", "index": 1, "position": 0}

data: {"type": "post_end", "index": 1, "content": "今天推荐这款运动鞋女2024新款时尚，百搭、舒适、时尚的设计真的很赞！适合日常穿搭，快来私信我了解更多～"}

data: {"type": "complete", "posts": [...]}
```

#### 工作原理

1. **接收请求**: API 层接收 SKU 和风格参数
2. **查询商品**: 从数据库查询商品信息（包含 tags 和 attributes）
3. **流式生成**: 使用 StreamingGenerator 逐字符/逐块生成文案
4. **实时返回**: 通过 SSE 实时推送生成的内容
5. **异步日志**: 后台记录 AI 任务日志到数据库

#### 特点

- ✅ **低延迟**: 第一个 chunk 在 500ms 内发出
- ✅ **流式体验**: 用户可以看到文案逐步生成
- ✅ **多风格**: 支持 natural（自然）、professional（专业）、funny（幽默）
- ✅ **自动日志**: 所有调用自动记录到 `ai_task_log` 表

#### 使用示例

**Python**:
```python
import httpx

response = httpx.post(
    "http://127.0.0.1:8000/ai/generate/copy",
    json={"sku": "8WZ01CM1", "style": "natural"},
    stream=True
)

for line in response.iter_lines():
    if line.startswith("data: "):
        data = json.loads(line[6:])
        print(data)
```

**JavaScript**:
```javascript
const eventSource = new EventSource('http://127.0.0.1:8000/ai/generate/copy', {
  method: 'POST',
  body: JSON.stringify({ sku: '8WZ01CM1', style: 'natural' })
});

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data);
};
```

---

### 2. 商品分析接口 (`/ai/analyze/product`)

#### 功能说明

基于规则逻辑分析商品，返回结构化的卖点、风格、场景等信息。

#### 请求示例

```bash
POST /ai/analyze/product
Content-Type: application/json

{
  "sku": "8WZ01CM1"
}
```

#### 响应示例

```json
{
  "core_selling_points": [
    "适配多场景穿搭",
    "舒适包裹，久穿不累",
    "时尚设计，提升气质"
  ],
  "style_tags": [
    "百搭",
    "时尚"
  ],
  "scene_suggestion": [
    "通勤",
    "逛街",
    "约会"
  ],
  "suitable_people": [
    "上班族",
    "年轻女性"
  ],
  "pain_points_solved": [
    "久走不累"
  ]
}
```

#### 工作原理

1. **接收请求**: API 层接收 SKU 参数
2. **查询商品**: 从数据库查询商品信息
3. **规则分析**: 基于 `product.tags` 和 `product.attributes` 应用规则逻辑
4. **生成结果**: 推导出核心卖点、风格标签、适用场景、适合人群、解决痛点
5. **返回结果**: 返回结构化的 JSON 响应

#### 规则示例

- **标签 "百搭"** → 添加 "适配多场景穿搭" 到 `core_selling_points`
- **标签 "软底" 或 "舒适"** → 添加 "久走不累" 到 `pain_points_solved`
- **属性 scene="通勤"** → 添加到 `scene_suggestion`
- **属性 season="四季"** → 添加 "通勤"、"逛街"、"约会" 到 `scene_suggestion`

详细规则说明请参考 [商品分析接口文档](docs/product_analyze_api.md)。

#### 使用示例

**Python**:
```python
import requests

response = requests.post(
    "http://127.0.0.1:8000/ai/analyze/product",
    json={"sku": "8WZ01CM1"}
)

result = response.json()
print("核心卖点:", result["core_selling_points"])
print("风格标签:", result["style_tags"])
```

**cURL**:
```bash
curl -X POST "http://127.0.0.1:8000/ai/analyze/product" \
  -H "Content-Type: application/json" \
  -d '{"sku": "8WZ01CM1"}'
```

---

## 数据库说明

### 表结构

项目包含以下主要数据表：

1. **products** - 商品信息表
   - 存储商品 SKU、名称、价格、标签、属性等

2. **guides** - 导购信息表
   - 存储导购 ID、姓名、门店、级别等

3. **user_behavior_logs** - 用户行为日志表
   - 记录用户浏览、收藏、分享等行为

4. **ai_task_log** - AI 任务日志表
   - 记录所有 AI 接口调用，包括输入、输出、耗时等

### 导入数据

#### 方法 1: 命令行导入

```bash
# 导入表结构
mysql -u root -p belle_ai < sql/schema.sql

# 导入种子数据
mysql -u root -p belle_ai < sql/seed_data.sql
```

#### 方法 2: MySQL 客户端工具

1. 打开 Navicat、DBeaver 等工具
2. 连接到 MySQL 数据库
3. 选择 `belle_ai` 数据库
4. 执行 `sql/schema.sql` 创建表
5. 执行 `sql/seed_data.sql` 导入数据

#### 方法 3: Python 脚本生成数据

如果需要重新生成种子数据：

```bash
python generate_seed_data.py
```

这会生成包含 100 个商品、50 个导购、1000+ 条行为日志的完整数据。

---

## 配置说明

### 环境变量

项目使用 `.env` 文件管理配置，参考 `.env.example` 创建：

```bash
# 数据库配置
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/belle_ai?charset=utf8mb4

# Redis 配置（可选）
REDIS_URL=redis://localhost:6379/0

# LLM 配置
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
LLM_MODEL=qwen-max

# 应用配置
APP_NAME=AI Smart Guide Service
APP_VERSION=1.0.0
APP_ENV=dev
LOG_LEVEL=info
```

### 配置项说明

| 配置项 | 说明 | 必填 |
|--------|------|------|
| DATABASE_URL | MySQL 数据库连接字符串 | 是 |
| REDIS_URL | Redis 连接字符串（V2+） | 否 |
| LLM_API_KEY | LLM API 密钥 | 否（使用 mock 模式） |
| LLM_BASE_URL | LLM API 基础 URL | 否 |
| LLM_MODEL | 使用的模型名称 | 否 |

---

## 开发指南

### 项目架构

项目采用分层架构：

```
API 层 (app/api/)
    ↓
Service 层 (app/services/)
    ↓
Repository 层 (app/repositories/)
    ↓
Model 层 (app/models/)
    ↓
Database (MySQL)
```

### 添加新接口

1. 在 `app/schemas/` 中定义请求/响应模型
2. 在 `app/api/v1/` 中创建路由
3. 在 `app/services/` 中实现业务逻辑
4. 在 `app/repositories/` 中实现数据访问（如需要）
5. 在 `app/main.py` 中注册路由

### 日志说明

项目使用 Python 标准 `logging` 模块，日志前缀说明：

- `[API]` - API 端点层
- `[SERVICE]` - 服务层
- `[REPOSITORY]` - 数据访问层
- `[GENERATOR]` - 生成器层
- `[LOG_SERVICE]` - 日志服务层

---

## 测试

### 健康检查

```bash
curl http://127.0.0.1:8000/health
```

### 测试文案生成

```bash
curl -X POST "http://127.0.0.1:8000/ai/generate/copy" \
  -H "Content-Type: application/json" \
  -d '{"sku": "8WZ01CM1", "style": "natural"}'
```

### 测试商品分析

```bash
curl -X POST "http://127.0.0.1:8000/ai/analyze/product" \
  -H "Content-Type: application/json" \
  -d '{"sku": "8WZ01CM1"}'
```

---

## 文档

- [产品需求文档 (PRD)](docs/PRD.md)
- [架构文档](docs/Architecture.md)
- [商品分析接口文档](docs/product_analyze_api.md)
- [Tags 查询说明](docs/tags_query_explanation.md)

---

## 版本规划

### V1 (当前版本)
- ✅ 商品文案生成（流式 SSE）
- ✅ 商品分析（规则驱动）
- ✅ 数据库表结构和种子数据
- ✅ AI 任务日志记录

### V2 (计划中)
- 🔲 RAG 向量检索（FAISS）
- 🔲 更丰富的商品理解
- 🔲 Redis 缓存

### V3 (计划中)
- 🔲 用户行为分析
- 🔲 智能跟进建议
- 🔲 防打扰机制

---

## 常见问题

### Q: 如何修改数据库连接？

A: 编辑 `.env` 文件中的 `DATABASE_URL` 配置项。

### Q: 如何查看 API 文档？

A: 启动服务后访问 http://127.0.0.1:8000/docs

### Q: 如何添加新的规则逻辑？

A: 编辑 `app/services/product_service.py` 中的 `analyze_product` 函数。

### Q: 如何切换 LLM 提供商？

A: 修改 `.env` 中的 `LLM_BASE_URL` 和 `LLM_API_KEY`，确保使用 OpenAI 兼容的 API。

---

## 许可证

本项目为内部项目，版权归公司所有。

---

## 联系方式

如有问题，请联系开发团队。

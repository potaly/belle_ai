# AI Smart Guide Service

智能导购服务 - 为鞋类零售行业提供 AI 驱动的销售助手服务

## 项目概述

AI Smart Guide Service 是一个基于 FastAPI 的智能导购服务，专为微信小程序等前端应用提供 AI 能力。服务通过分析商品信息和用户行为，为导购人员生成朋友圈文案、分析商品卖点，帮助提升销售效率。

**V4 版本升级**：系统从"两个 API + RAG + 意图判断"升级为"一个可规划、可执行、多智能体协作的完整自动化销售 Agent"。

### 技术栈

- **Web 框架**: FastAPI (Python 3.10+)
- **ORM**: SQLAlchemy 2.0
- **数据库**: MySQL 8.0+
- **缓存**: Redis (可选，V2+)
- **向量数据库**: FAISS (V2+)
- **AI 模型**: 支持阿里百炼、DeepSeek、Qwen、OpenAI 等
- **Agent 框架**: LangGraph (V4+)
- **异步支持**: asyncio, httpx

---

## 功能特性

### V1 功能

#### 1. 商品文案生成 (`POST /ai/generate/copy`)
- **流式响应**: 使用 Server-Sent Events (SSE) 实时返回生成内容
- **低延迟**: 第一个 chunk 在 500ms 内发出
- **多风格支持**: 自然、专业、幽默三种文案风格
- **异步日志**: 自动记录 AI 任务日志到数据库

#### 2. 商品分析 (`POST /ai/analyze/product`)
- **规则驱动**: 基于商品标签和属性智能分析
- **结构化输出**: 返回核心卖点、风格标签、适用场景、适合人群、解决痛点
- **自动推导**: 从 tags 和 attributes 自动推导分析结果

#### 3. 数据管理
- **商品管理**: 支持商品信息存储和查询
- **行为日志**: 记录用户浏览、收藏等行为
- **AI 日志**: 记录所有 AI 调用任务，便于分析和优化

---

### V2 功能

#### 1. 向量语义搜索 (`POST /ai/vector/search`)
- **语义理解**: 使用阿里百炼嵌入模型，理解用户意图
- **智能检索**: 基于 FAISS 向量数据库，快速搜索相似商品
- **混合搜索**: 结合 SKU 精确匹配、关键词匹配和向量相似度
- **中文优化**: 使用 `text-embedding-v2` 模型，对中文支持优秀
- **灵活配置**: 支持自定义返回结果数量（top_k）

#### 2. RAG 知识库
- **自动分块**: 将商品文本智能分割成小块（约 300 字符，50 字符重叠）
- **向量索引**: 使用 FAISS 构建高效的向量索引
- **持久化存储**: 索引保存到磁盘，支持快速加载
- **自然语言转换**: 将结构化商品数据转换为自然语言描述

#### 3. RAG 调试端点 (`POST /admin/rag/preview`)
- **调试模式**: 仅在 `DEBUG=true` 时可用
- **详细输出**: 显示原始搜索结果和处理后的结果
- **关键词提取**: 显示提取的关键词和 SKU
- **匹配分析**: 显示匹配类型和评分详情

#### 4. 初始化工具
- **一键初始化**: 从 MySQL 数据库自动构建向量索引
- **批量处理**: 支持大量商品数据的批量处理
- **进度显示**: 实时显示初始化进度和统计信息

---

### V3 功能

#### 1. 用户行为分析
- **行为仓库** (`BehaviorRepository`): 高效查询用户行为日志
- **行为摘要**: 自动汇总访问次数、停留时间、事件类型等
- **意图分析引擎** (`IntentEngine`): 基于行为数据智能判断用户购买意图
- **意图级别**: `high`、`medium`、`low`、`hesitating` 四级分类

#### 2. 意图分析 API (`POST /ai/analyze/intent`)
- **自动分析**: 根据用户行为日志自动分析购买意图
- **详细原因**: 提供意图分类的文本原因说明
- **行为摘要**: 返回完整的行为统计数据

#### 3. 跟进建议服务 (`FollowupService`)
- **混合策略**: 规则驱动 + LLM 生成
- **个性化消息**: 根据用户意图生成个性化跟进建议
- **反打扰机制**: 低意图用户自动跳过主动接触

#### 4. 跟进建议 API (`POST /ai/followup/suggest`)
- **智能建议**: 自动生成跟进动作和消息
- **动作类型**: `send_coupon`、`ask_size`、`remind_stock` 等
- **个性化文案**: 结合商品信息和用户行为生成文案

---

### V4 功能（AI Agent 系统）

#### 1. 核心 Agent 框架
- **AgentContext**: 统一上下文管理，支持状态和消息记忆
- **AgentRunner**: Agent 节点执行器，提供日志和错误处理
- **模块化设计**: 清晰的职责分离，易于扩展

#### 2. Agent 工具层
- **ProductTool**: 获取商品信息
- **BehaviorTool**: 获取和汇总用户行为
- **RAGTool**: 检索 RAG 上下文
- **CopyTool**: 生成营销文案

#### 3. Planner Agent
- **智能规划**: 根据上下文动态生成执行计划
- **规则驱动**: 基于业务规则决定任务顺序
- **条件跳过**: 根据意图级别和反打扰规则跳过不必要任务

#### 4. Worker Agents
- **IntentAgent**: 意图分类节点
- **CopyAgent**: 文案生成节点
- **SalesAgent**: 反打扰检查节点

#### 5. LangGraph 状态机
- **状态机编排**: 使用 LangGraph 编排完整销售流程
- **条件路由**: 根据业务规则动态决定执行路径
- **提前结束**: 反打扰机制支持提前结束流程

#### 6. 销售流程图 API (`POST /ai/sales/graph`)
- **完整流程**: 执行 LangGraph 定义的完整销售流程
- **自定义计划**: 支持使用 Planner 生成的自定义计划
- **详细日志**: 完整的执行日志和统计信息

#### 7. AI 智能销售 Agent API (`POST /ai/agent/sales_flow`) ⭐ **V4 最终产物**
- **完整自动化**: 一个 API 调用完成全流程
- **智能编排**: 自动规划、执行、协调所有 Agent 节点
- **完整结果**: 返回商品信息、行为摘要、意图分析、生成文案等完整结果
- **生产就绪**: 可直接用于生产环境的完整 Agent 系统

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
│   │       ├── copy.py         # 文案生成接口 (V1)
│   │       ├── product.py      # 商品分析接口 (V1)
│   │       ├── vector_search.py # 向量搜索接口 (V2)
│   │       ├── rag_debug.py    # RAG 调试接口 (V2)
│   │       ├── intent.py       # 意图分析接口 (V3)
│   │       ├── followup.py     # 跟进建议接口 (V3)
│   │       ├── sales_graph.py  # 销售流程图接口 (V4)
│   │       └── agent_sales_flow.py # AI智能销售Agent接口 (V4)
│   ├── models/                  # ORM 模型
│   │   ├── product.py          # 商品模型
│   │   ├── guide.py            # 导购模型
│   │   ├── user_behavior_log.py # 用户行为日志模型
│   │   └── ai_task_log.py      # AI 任务日志模型
│   ├── schemas/                 # Pydantic 模型
│   │   ├── copy_schemas.py     # 文案生成请求/响应
│   │   ├── product_schemas.py  # 商品分析请求/响应
│   │   ├── intent_schemas.py   # 意图分析请求/响应
│   │   ├── followup_schemas.py # 跟进建议请求/响应
│   │   ├── sales_graph_schemas.py # 销售流程图请求/响应
│   │   └── agent_sales_flow_schemas.py # Agent请求/响应
│   ├── services/                # 业务逻辑层
│   │   ├── copy_service.py     # 文案生成服务
│   │   ├── product_service.py  # 商品分析服务
│   │   ├── log_service.py      # 日志服务
│   │   ├── llm_client.py       # LLM 客户端封装
│   │   ├── embedding_client.py  # 嵌入模型客户端 (V2)
│   │   ├── vector_store.py     # 向量存储服务 (V2)
│   │   ├── rag_service.py      # RAG 服务 (V2)
│   │   ├── prompt_builder.py   # 提示词构建器 (V2)
│   │   ├── intent_engine.py    # 意图分析引擎 (V3)
│   │   └── followup_service.py # 跟进建议服务 (V3)
│   ├── repositories/             # 数据访问层
│   │   ├── product_repository.py # 商品数据访问
│   │   └── behavior_repository.py # 行为日志访问 (V3)
│   ├── agents/                  # Agent 系统 (V4)
│   │   ├── context.py          # Agent 上下文
│   │   ├── agent_runner.py     # Agent 执行器
│   │   ├── planner_agent.py     # 规划器
│   │   ├── tools/              # Agent 工具
│   │   │   ├── product_tool.py
│   │   │   ├── behavior_tool.py
│   │   │   ├── rag_tool.py
│   │   │   └── copy_tool.py
│   │   ├── workers/            # Worker Agents
│   │   │   ├── intent_agent.py
│   │   │   ├── copy_agent.py
│   │   │   └── sales_agent.py
│   │   └── graph/              # LangGraph 状态机
│   │       └── sales_graph.py
│   ├── db/                      # 数据库初始化
│   │   └── init_vector_store.py # 向量索引初始化 (V2)
│   └── utils/                   # 工具函数
│       └── chunk_utils.py       # 文本分块工具 (V2)
├── sql/                          # SQL 脚本
│   ├── schema.sql               # 数据库表结构
│   └── seed_data.sql            # 种子数据
├── docs/                         # 文档
│   ├── PRD.md                   # 产品需求文档
│   ├── Architecture.md          # 架构文档
│   ├── product_analyze_api.md   # 商品分析接口文档
│   ├── vector_search_api.md     # 向量搜索接口文档
│   ├── intent_analysis_api.md   # 意图分析接口文档
│   ├── followup_api.md          # 跟进建议接口文档
│   ├── sales_graph_api.md       # 销售流程图接口文档
│   └── agent_sales_flow_api.md  # AI智能销售Agent接口文档
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
# 数据库配置
DATABASE_URL=mysql+pymysql://user:password@localhost:3306/belle_ai

# Redis 配置（可选）
REDIS_URL=redis://localhost:6379/0

# LLM 配置
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.example.com/v1
LLM_MODEL_NAME=qwen3-max

# 嵌入模型配置（V2+）
EMBEDDING_API_KEY=your_embedding_api_key
EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
EMBEDDING_MODEL=text-embedding-v2

# 调试模式（可选）
DEBUG=false
```

### 4. 初始化数据库

```bash
# 创建数据库表
mysql -u root -p < sql/schema.sql

# 导入种子数据
mysql -u root -p < sql/seed_data.sql
```

### 5. 初始化向量索引（V2+）

```bash
# 从数据库构建向量索引
python app/db/init_vector_store.py
```

### 6. 启动服务

```bash
# 使用 uvicorn 启动
uvicorn app.main:app --reload

# 或使用 Python 直接运行
python -m uvicorn app.main:app --reload
```

服务将在 `http://127.0.0.1:8000` 启动。

---

## API 文档

### 在线文档

启动服务后，访问以下地址查看 API 文档：

- **Swagger UI**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

### 主要 API 端点

#### V1 API

- `POST /ai/generate/copy` - 生成朋友圈文案（流式）
- `POST /ai/analyze/product` - 分析商品卖点

#### V2 API

- `POST /ai/vector/search` - 向量语义搜索
- `GET /ai/vector/stats` - 向量索引统计
- `POST /admin/rag/preview` - RAG 调试预览（仅 DEBUG 模式）

#### V3 API

- `POST /ai/analyze/intent` - 分析用户购买意图
- `POST /ai/followup/suggest` - 生成跟进建议

#### V4 API

- `POST /ai/sales/graph` - 执行销售流程图
- `GET /ai/sales/graph/health` - 销售图健康检查
- `POST /ai/agent/sales_flow` ⭐ - **AI 智能销售 Agent（推荐使用）**

### 详细文档

- [商品分析 API](./docs/product_analyze_api.md)
- [向量搜索 API](./docs/vector_search_api.md)
- [意图分析 API](./docs/intent_analysis_api.md)
- [跟进建议 API](./docs/followup_api.md)
- [销售流程图 API](./docs/sales_graph_api.md)
- [AI 智能销售 Agent API](./docs/agent_sales_flow_api.md) ⭐

---

## 使用示例

### 1. 生成朋友圈文案（V1）

```bash
curl -X POST "http://127.0.0.1:8000/ai/generate/copy" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "8WZ01CM1",
    "style": "natural"
  }'
```

### 2. 分析商品卖点（V1）

```bash
curl -X POST "http://127.0.0.1:8000/ai/analyze/product" \
  -H "Content-Type: application/json" \
  -d '{
    "sku": "8WZ01CM1"
  }'
```

### 3. 向量语义搜索（V2）

```bash
curl -X POST "http://127.0.0.1:8000/ai/vector/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "舒适的运动鞋",
    "top_k": 5
  }'
```

### 4. 分析用户意图（V3）

```bash
curl -X POST "http://127.0.0.1:8000/ai/analyze/intent" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "limit": 50
  }'
```

### 5. AI 智能销售 Agent（V4）⭐ **推荐**

```bash
curl -X POST "http://127.0.0.1:8000/ai/agent/sales_flow" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "guide_id": "guide_001",
    "sku": "8WZ01CM1"
  }'
```

**响应示例**：

```json
{
  "success": true,
  "message": "Agent sales flow executed successfully",
  "data": {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "product": {
      "name": "跑鞋女2024新款舒适",
      "price": 398.0,
      "tags": ["舒适", "轻便", "透气"]
    },
    "behavior_summary": {
      "visit_count": 2,
      "max_stay_seconds": 25,
      "has_enter_buy_page": true
    },
    "intent": {
      "level": "high",
      "reason": "用户已进入购买页面，这是强烈的购买信号。"
    },
    "allowed": true,
    "rag_used": true,
    "messages": [
      {
        "role": "assistant",
        "content": "这是一款舒适的跑鞋，采用网面材质，透气轻便..."
      }
    ],
    "plan_executed": [
      "fetch_product",
      "fetch_behavior_summary",
      "classify_intent",
      "anti_disturb_check",
      "retrieve_rag",
      "generate_copy"
    ]
  }
}
```

---

## V4 Agent 系统架构

### 核心组件

1. **AgentContext**: 统一上下文管理
   - 存储用户信息、商品信息、行为摘要、意图级别等
   - 维护消息历史和额外数据

2. **Planner Agent**: 智能任务规划
   - 根据上下文动态生成执行计划
   - 支持条件跳过和优化

3. **Tools**: 可复用的工具函数
   - ProductTool: 获取商品
   - BehaviorTool: 获取行为摘要
   - RAGTool: 检索上下文
   - CopyTool: 生成文案

4. **Workers**: 独立的工作节点
   - IntentAgent: 意图分类
   - CopyAgent: 文案生成
   - SalesAgent: 反打扰检查

5. **LangGraph**: 状态机编排
   - 定义完整的执行流程
   - 支持条件路由和提前结束

### 执行流程

```
初始化 Context
  ↓
Planner 生成计划
  ↓
LangGraph 执行流程
  ├─ fetch_product
  ├─ fetch_behavior_summary
  ├─ classify_intent
  ├─ anti_disturb_check
  │   ├─ 拒绝 → END
  │   └─ 允许 → 继续
  ├─ retrieve_rag (可选)
  └─ generate_copy
  ↓
返回完整结果
```

---

## 开发指南

### 添加新的 Agent 工具

1. 在 `app/agents/tools/` 创建工具文件
2. 实现工具函数：`async def tool_name(context, **kwargs) -> AgentContext`
3. 在 `app/agents/tools/__init__.py` 导出
4. 在 Planner 或 Graph 中使用

### 添加新的 Worker Agent

1. 在 `app/agents/workers/` 创建节点文件
2. 实现节点函数：`async def node_name(context, **kwargs) -> AgentContext`
3. 在 `app/agents/workers/__init__.py` 导出
4. 在 Planner 或 Graph 中注册

### 修改执行流程

1. 修改 `app/agents/planner_agent.py` 调整规划逻辑
2. 修改 `app/agents/graph/sales_graph.py` 调整图结构
3. 更新相关文档

---

## 测试

### 运行测试脚本

```bash
# 测试向量搜索
python test_vector_search.py

# 测试意图分析
python test_intent_engine.py

# 测试跟进建议
python test_followup_service.py

# 测试 Agent 系统
python test_agent_framework.py
python test_agent_tools.py
python test_planner_agent.py
python test_worker_agents.py
python test_sales_graph.py
```

---

## 监控和日志

### 健康检查

```bash
# 服务健康检查
curl http://127.0.0.1:8000/health

# 销售图健康检查
curl http://127.0.0.1:8000/ai/sales/graph/health
```

### 日志

所有日志输出到控制台，包括：
- API 请求日志
- Agent 执行日志
- 数据库操作日志
- LLM 调用日志

---

## 版本历史

- **v4.0.4**: AI 智能销售 Agent API（V4 最终产物）
- **v4.0.3**: LangGraph 销售流程图和 API
- **v4.0.2**: Worker Agent 节点
- **v4.0.1**: Agent 工具层和规划器
- **v4.0.0**: 核心 Agent 框架
- **v3.0.0**: 用户行为分析和跟进建议
- **v2.0.2**: RAG 知识库和向量搜索
- **v1.0.0**: 基础文案生成和商品分析

---

## 贡献指南

1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 许可证

本项目采用 MIT 许可证。

---

## 联系方式

如有问题或建议，请提交 Issue 或联系项目维护者。

---

**最后更新**: 2025-12-04  
**当前版本**: v4.0.4

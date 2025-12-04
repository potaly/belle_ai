# AI 智能销售 Agent API 文档

## 概述

这是 **V4 版本的最终产物**：一个完整的 AI 智能销售 Agent API，整合了所有 V4 功能：

- **AgentContext**: 上下文管理
- **Planner**: 智能任务规划
- **Tools**: 工具调用（商品、行为、RAG、文案）
- **Workers**: 工作节点（意图分类、反打扰检查、文案生成）
- **LangGraph**: 状态机编排

**系统从"两个 API + RAG + 意图判断"升级为：一个可规划、可执行、多智能体协作的完整自动化销售 Agent。**

---

## 接口信息

### 执行 AI 智能销售 Agent 流程

**端点**: `POST /ai/agent/sales_flow`

**描述**: 执行完整的 AI 智能销售 Agent 流程，自动完成从商品分析到文案生成的全流程。

---

## 请求参数

### 请求体

```json
{
  "user_id": "user_001",
  "guide_id": "guide_001",
  "sku": "8WZ01CM1"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `guide_id` | string | 否 | 导购 ID（可选） |
| `sku` | string | 是 | 商品 SKU |

---

## 响应格式

### 成功响应 (200 OK)

```json
{
  "success": true,
  "message": "Agent sales flow executed successfully",
  "data": {
    "user_id": "user_001",
    "guide_id": "guide_001",
    "sku": "8WZ01CM1",
    "execution_time_seconds": 2.456,
    "product": {
      "name": "跑鞋女2024新款舒适",
      "price": 398.0,
      "tags": ["舒适", "轻便", "透气"],
      "sku": "8WZ01CM1"
    },
    "behavior_summary": {
      "visit_count": 2,
      "max_stay_seconds": 25,
      "avg_stay_seconds": 20.0,
      "total_stay_seconds": 45,
      "has_enter_buy_page": true,
      "has_favorite": false,
      "has_share": false,
      "has_click_size_chart": false,
      "event_types": ["browse", "enter_buy_page"]
    },
    "intent": {
      "level": "high",
      "reason": "用户已进入购买页面，这是强烈的购买信号。访问次数：2次，最大停留：25秒"
    },
    "allowed": true,
    "anti_disturb_blocked": false,
    "rag_used": true,
    "rag_chunks_count": 3,
    "messages": [
      {
        "role": "assistant",
        "content": "这是一款舒适的跑鞋，采用网面材质，透气轻便，适合四季运动穿着。价格为398元。"
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

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否执行成功 |
| `message` | string | 响应消息 |
| `data.user_id` | string | 用户 ID |
| `data.guide_id` | string | 导购 ID |
| `data.sku` | string | 商品 SKU |
| `data.execution_time_seconds` | float | 执行时间（秒） |
| `data.product` | object | 商品信息 |
| `data.product.name` | string | 商品名称 |
| `data.product.price` | float | 商品价格 |
| `data.product.tags` | array | 商品标签列表 |
| `data.behavior_summary` | object | 用户行为摘要 |
| `data.intent` | object | 意图分析结果 |
| `data.intent.level` | string | 意图级别：`high`、`medium`、`low`、`hesitating` |
| `data.intent.reason` | string | 意图分类原因 |
| `data.allowed` | boolean | 是否允许主动接触用户 |
| `data.anti_disturb_blocked` | boolean | 是否被反打扰机制阻止 |
| `data.rag_used` | boolean | 是否使用了 RAG 检索 |
| `data.rag_chunks_count` | integer | RAG 上下文片段数量 |
| `data.messages` | array | 生成的消息列表 |
| `data.messages[].role` | string | 消息角色：`system`、`user`、`assistant` |
| `data.messages[].content` | string | 消息内容 |
| `data.plan_executed` | array | 执行的计划节点列表 |

---

## 执行流程

### 完整 Agent 流程

```
1. 初始化 AgentContext
   ↓
2. 使用 Planner 生成执行计划
   ↓
3. 执行 LangGraph 销售流程图
   ├─ fetch_product (获取商品信息)
   ├─ fetch_behavior_summary (获取行为摘要)
   ├─ classify_intent (分类意图)
   ├─ anti_disturb_check (反打扰检查)
   │   ├─ 如果拒绝 → END
   │   └─ 如果允许 → 继续
   ├─ retrieve_rag (检索 RAG 上下文，可选)
   └─ generate_copy (生成营销文案)
   ↓
4. 返回完整结果摘要
```

### 智能决策

- **意图级别判断**: 根据用户行为自动分类意图
- **反打扰机制**: 低意图用户自动跳过主动接触
- **RAG 检索**: 低意图用户跳过 RAG，直接生成文案
- **动态规划**: Planner 根据上下文动态生成执行计划

---

## 使用示例

### cURL

```bash
curl -X POST "http://127.0.0.1:8000/ai/agent/sales_flow" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "guide_id": "guide_001",
    "sku": "8WZ01CM1"
  }'
```

### Python

```python
import httpx

response = httpx.post(
    "http://127.0.0.1:8000/ai/agent/sales_flow",
    json={
        "user_id": "user_001",
        "guide_id": "guide_001",
        "sku": "8WZ01CM1",
    },
)

result = response.json()
if result["success"]:
    data = result["data"]
    print(f"商品: {data['product']['name']}")
    print(f"意图级别: {data['intent']['level']}")
    print(f"生成的文案: {data['messages'][-1]['content']}")
```

### Postman

1. **创建新请求**
   - Method: `POST`
   - URL: `http://127.0.0.1:8000/ai/agent/sales_flow`

2. **设置 Headers**
   - `Content-Type: application/json`

3. **设置 Body (raw JSON)**
   ```json
   {
     "user_id": "user_001",
     "guide_id": "guide_001",
     "sku": "8WZ01CM1"
   }
   ```

4. **发送请求并查看响应**

---

## 与其他 API 的区别

### 对比 `/ai/sales/graph`

| 特性 | `/ai/agent/sales_flow` | `/ai/sales/graph` |
|------|------------------------|-------------------|
| **定位** | V4 最终产物，完整 Agent 系统 | LangGraph 状态机执行 |
| **规划** | 自动使用 Planner 生成计划 | 可手动指定计划或使用完整流程 |
| **返回内容** | 完整的结构化结果摘要 | 执行结果和统计信息 |
| **使用场景** | 生产环境，完整自动化流程 | 调试、测试、自定义流程 |

### 对比 V3 API

| 特性 | `/ai/agent/sales_flow` | V3 API (`/ai/analyze/intent`, `/ai/followup/suggest`) |
|------|------------------------|------------------------------------------------------|
| **架构** | 多智能体协作系统 | 独立功能模块 |
| **流程** | 自动编排完整流程 | 需要多次调用 |
| **上下文** | AgentContext 统一管理 | 无统一上下文 |
| **规划** | 智能任务规划 | 无规划能力 |

---

## 业务逻辑说明

### 意图级别

- **high**: 高意图用户，已进入购买页面或停留时间较长
- **medium**: 中等意图用户，多次访问或停留时间适中
- **low**: 低意图用户，访问次数少且停留时间短
- **hesitating**: 犹豫用户，多次访问但无明确行动

### 反打扰机制

- **高/中等意图**: 允许主动接触，继续执行后续节点
- **犹豫用户**: 允许温和接触
- **低意图**: 不建议主动打扰，提前结束流程

### RAG 检索策略

- **低意图用户**: 跳过 RAG 检索，直接生成文案
- **其他用户**: 先检索 RAG 上下文，再生成文案

---

## 错误处理

### 常见错误

1. **商品不存在** (500)
   - 错误信息: `Product not found: <sku>`
   - 解决方案: 检查 SKU 是否正确

2. **数据库连接失败** (500)
   - 错误信息: `Database connection failed`
   - 解决方案: 检查数据库配置和连接

3. **LLM 调用失败** (500)
   - 错误信息: `LLM stream transport error`
   - 解决方案: 检查 LLM API 配置和网络连接

---

## 性能指标

- **平均执行时间**: 2-5 秒（取决于 LLM 响应时间）
- **并发支持**: 支持异步并发请求
- **资源消耗**: 每个请求会创建数据库会话和 LLM 连接

---

## V4 架构优势

### 1. 模块化设计

- **Context**: 统一上下文管理
- **Planner**: 智能任务规划
- **Tools**: 可复用的工具函数
- **Workers**: 独立的工作节点
- **Graph**: 状态机编排

### 2. 可扩展性

- 新增工具：只需实现工具函数并注册
- 新增节点：只需实现节点函数并添加到图
- 修改流程：只需修改 Planner 或图的边

### 3. 可观测性

- 详细的执行日志
- 完整的执行计划记录
- 每个节点的执行时间统计

### 4. 智能决策

- 基于上下文的动态规划
- 自动反打扰机制
- 智能 RAG 检索策略

---

## 相关文档

- [销售流程图 API](./sales_graph_api.md)
- [意图分析 API](./intent_analysis_api.md)
- [跟进建议 API](./followup_api.md)
- [Agent 框架文档](../app/agents/README.md)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)

---

## 更新日志

- **v4.0.4**: 添加 AI 智能销售 Agent API（V4 最终产物）


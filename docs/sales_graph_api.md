# 销售流程图 API 文档

## 概述

销售流程图 API 使用 LangGraph 状态机来编排整个销售流程，包括商品信息获取、用户行为分析、意图分类、反打扰检查和营销文案生成。

**V4 功能特性**：基于 LangGraph 的智能 Agent 编排系统。

---

## 接口列表

### 1. 执行销售流程图

**端点**: `POST /ai/sales/graph`

**描述**: 执行完整的销售流程图，自动编排所有 Agent 节点。

#### 请求参数

```json
{
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "guide_id": "guide_001",
  "use_custom_plan": false
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `user_id` | string | 是 | 用户 ID |
| `sku` | string | 是 | 商品 SKU |
| `guide_id` | string | 否 | 导购 ID（可选） |
| `use_custom_plan` | boolean | 否 | 是否使用规划器生成自定义计划（默认 false，使用完整图流程） |

#### 响应示例

**成功响应** (200 OK):

```json
{
  "success": true,
  "message": "Sales graph executed successfully",
  "data": {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "intent_level": "high",
    "allowed": true,
    "anti_disturb_blocked": false,
    "messages_count": 2,
    "rag_chunks_count": 3,
    "execution_time_seconds": 2.456,
    "plan_used": ["fetch_product", "fetch_behavior_summary", "classify_intent", "anti_disturb_check", "retrieve_rag", "generate_copy"],
    "intent_reason": "用户已进入购买页面，这是强烈的购买信号。访问次数：2次，最大停留：25秒",
    "final_message": "这是一款舒适的跑鞋，采用网面材质，透气轻便，适合四季运动穿着。价格为398元。",
    "product_name": "跑鞋女2024新款舒适",
    "product_price": 398.0
  }
}
```

**错误响应** (500 Internal Server Error):

```json
{
  "detail": "Sales graph execution failed: <error message>"
}
```

#### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 是否执行成功 |
| `message` | string | 响应消息 |
| `data.user_id` | string | 用户 ID |
| `data.sku` | string | 商品 SKU |
| `data.intent_level` | string | 意图级别：`high`、`medium`、`low`、`hesitating` |
| `data.allowed` | boolean | 是否允许主动接触用户 |
| `data.anti_disturb_blocked` | boolean | 是否被反打扰机制阻止 |
| `data.messages_count` | integer | 生成的消息数量 |
| `data.rag_chunks_count` | integer | 检索到的 RAG 上下文片段数量 |
| `data.execution_time_seconds` | float | 执行时间（秒） |
| `data.plan_used` | array/string | 使用的执行计划（数组或 "full_graph_flow"） |
| `data.intent_reason` | string | 意图分类的原因说明 |
| `data.final_message` | string | 最后生成的消息（通常是营销文案） |
| `data.product_name` | string | 商品名称 |
| `data.product_price` | float | 商品价格 |

---

### 2. 健康检查

**端点**: `GET /ai/sales/graph/health`

**描述**: 检查销售图服务的健康状态。

#### 响应示例

```json
{
  "status": "ok",
  "graph_compiled": true,
  "message": "Sales graph service is healthy"
}
```

---

## 执行流程

### 完整图流程（`use_custom_plan: false`）

```
1. fetch_product (获取商品信息)
   ↓
2. fetch_behavior_summary (获取行为摘要)
   ↓
3. classify_intent (分类意图)
   ↓
4. anti_disturb_check (反打扰检查)
   ↓
   ├─ 如果反打扰拒绝 → END
   ├─ 如果低意图 → generate_copy → END
   └─ 其他情况 → retrieve_rag → generate_copy → END
```

### 自定义计划流程（`use_custom_plan: true`）

使用 `PlannerAgent` 根据当前上下文动态生成执行计划，然后按计划顺序执行节点。

---

## 使用示例

### cURL

```bash
# 执行完整图流程
curl -X POST "http://127.0.0.1:8000/ai/sales/graph" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "guide_id": "guide_001",
    "use_custom_plan": false
  }'

# 使用自定义计划
curl -X POST "http://127.0.0.1:8000/ai/sales/graph" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "use_custom_plan": true
  }'

# 健康检查
curl -X GET "http://127.0.0.1:8000/ai/sales/graph/health"
```

### Python

```python
import httpx

# 执行完整图流程
response = httpx.post(
    "http://127.0.0.1:8000/ai/sales/graph",
    json={
        "user_id": "user_001",
        "sku": "8WZ01CM1",
        "guide_id": "guide_001",
        "use_custom_plan": False,
    },
)
result = response.json()
print(f"意图级别: {result['data']['intent_level']}")
print(f"生成的文案: {result['data']['final_message']}")
```

### Postman

1. **创建新请求**
   - Method: `POST`
   - URL: `http://127.0.0.1:8000/ai/sales/graph`

2. **设置 Headers**
   - `Content-Type: application/json`

3. **设置 Body (raw JSON)**
   ```json
   {
     "user_id": "user_001",
     "sku": "8WZ01CM1",
     "guide_id": "guide_001",
     "use_custom_plan": false
   }
   ```

4. **发送请求并查看响应**

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

### RAG 检索

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

## 相关文档

- [Agent 框架文档](../app/agents/README.md)
- [意图分析 API](./intent_analysis_api.md)
- [跟进建议 API](./followup_api.md)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)

---

## 更新日志

- **v4.0.3**: 添加销售流程图 API，支持 LangGraph 状态机编排


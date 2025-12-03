# 跟进建议 API 接口文档

## 概述

跟进建议 API 是 V3 版本的核心功能，用于根据用户的购买意图和行为数据，生成个性化的跟进建议和消息。该接口结合了意图分析引擎和 LLM，提供智能化的销售跟进策略。

## 端点信息

- **URL**: `POST /ai/followup/suggest`
- **标签**: `ai`, `followup`
- **版本**: V3.0.0

## 请求格式

### 请求体

```json
{
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "limit": 50
}
```

### 字段说明

| 字段 | 类型 | 必填 | 说明 | 默认值 |
|------|------|------|------|--------|
| `user_id` | string | 是 | 用户ID | - |
| `sku` | string | 是 | 商品SKU | - |
| `limit` | integer | 否 | 分析的行为日志数量上限 | 50 |

### 字段约束

- `user_id`: 最少 1 个字符
- `sku`: 最少 1 个字符
- `limit`: 范围 1-100

## 响应格式

### 成功响应 (200)

```json
{
  "success": true,
  "message": "跟进建议生成成功",
  "data": {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "product_name": "舒适跑鞋",
    "intention_level": "high",
    "suggested_action": "ask_size",
    "message": "您好！看到您对这款舒适跑鞋很感兴趣，需要我帮您推荐合适的尺码吗？",
    "behavior_summary": {
      "visit_count": 2,
      "max_stay_seconds": 30,
      "avg_stay_seconds": 20.0,
      "total_stay_seconds": 40,
      "has_enter_buy_page": true,
      "has_favorite": false,
      "has_share": false,
      "has_click_size_chart": false,
      "event_types": ["browse", "enter_buy_page"]
    },
    "total_logs_analyzed": 2
  }
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | boolean | 请求是否成功 |
| `message` | string | 响应消息 |
| `data` | object | 跟进建议数据 |
| `data.user_id` | string | 用户ID |
| `data.sku` | string | 商品SKU |
| `data.product_name` | string | 商品名称 |
| `data.intention_level` | string | 意图级别：`high`, `medium`, `low`, `hesitating` |
| `data.suggested_action` | string | 建议动作类型 |
| `data.message` | string | 个性化跟进消息 |
| `data.behavior_summary` | object | 行为摘要数据（如果无行为记录则为 null） |
| `data.total_logs_analyzed` | integer | 分析的行为日志总数 |

### suggested_action 说明

| 动作类型 | 说明 | 触发条件 |
|---------|------|---------|
| `ask_size` | 询问是否需要尺码推荐 | 意图级别 = `high` |
| `send_coupon` | 发送限时优惠券 | 意图级别 = `medium` |
| `explain_benefits` | 解释产品优势并温和推动 | 意图级别 = `hesitating` |
| `passive_message` | 发送被动友好消息（不打扰） | 意图级别 = `low` |

## Postman 测试指南

### 1. 创建请求

1. 打开 Postman
2. 创建新请求
3. 设置请求方法为 `POST`
4. 设置 URL: `http://127.0.0.1:8000/ai/followup/suggest`

### 2. 设置请求头

```
Content-Type: application/json
```

### 3. 设置请求体

选择 **Body** → **raw** → **JSON**，输入：

```json
{
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "limit": 50
}
```

### 4. 发送请求

点击 **Send** 按钮发送请求。

### 5. 查看响应

成功响应示例：

```json
{
  "success": true,
  "message": "跟进建议生成成功",
  "data": {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "product_name": "舒适跑鞋",
    "intention_level": "high",
    "suggested_action": "ask_size",
    "message": "您好！看到您对这款舒适跑鞋很感兴趣，需要我帮您推荐合适的尺码吗？",
    "behavior_summary": {
      "visit_count": 2,
      "max_stay_seconds": 30,
      "avg_stay_seconds": 20.0,
      "has_enter_buy_page": true,
      "has_favorite": false,
      "has_share": false,
      "has_click_size_chart": false,
      "event_types": ["browse", "enter_buy_page"]
    },
    "total_logs_analyzed": 2
  }
}
```

## 测试用例

### 测试用例 1: 高意图用户（进入购买页）

**请求**:
```json
{
  "user_id": "user_003",
  "sku": "8WZ03CM3",
  "limit": 50
}
```

**预期响应**:
- `intention_level`: `"high"`
- `suggested_action`: `"ask_size"`
- `has_enter_buy_page`: `true`

### 测试用例 2: 中等意图用户（多次访问）

**请求**:
```json
{
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "limit": 50
}
```

**预期响应**:
- `intention_level`: `"medium"` 或 `"high"`（取决于具体行为）
- `suggested_action`: `"send_coupon"` 或 `"ask_size"`

### 测试用例 3: 低意图用户（无行为记录）

**请求**:
```json
{
  "user_id": "user_999",
  "sku": "8WZ01CM1",
  "limit": 50
}
```

**预期响应**:
- `intention_level`: `"low"`
- `suggested_action`: `"passive_message"`
- `behavior_summary`: `null`
- `total_logs_analyzed`: `0`

### 测试用例 4: 犹豫用户（多次访问但无行动）

**请求**:
```json
{
  "user_id": "user_002",
  "sku": "8WZ02CM2",
  "limit": 50
}
```

**预期响应**:
- `intention_level`: `"hesitating"`（如果符合条件）
- `suggested_action`: `"explain_benefits"`

## cURL 示例

```bash
curl -X POST "http://127.0.0.1:8000/ai/followup/suggest" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "limit": 50
  }'
```

## Python 示例

```python
import requests

url = "http://127.0.0.1:8000/ai/followup/suggest"
payload = {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "limit": 50
}

response = requests.post(url, json=payload)
data = response.json()

if data["success"]:
    result = data["data"]
    print(f"意图级别: {result['intention_level']}")
    print(f"建议动作: {result['suggested_action']}")
    print(f"跟进消息: {result['message']}")
else:
    print(f"错误: {data['message']}")
```

## 错误响应

### 400 Bad Request - 参数验证失败

```json
{
  "detail": [
    {
      "loc": ["body", "user_id"],
      "msg": "ensure this value has at least 1 characters",
      "type": "value_error.any_str.min_length"
    }
  ]
}
```

### 404 Not Found - 商品不存在

```json
{
  "detail": "Product with SKU 8WZ99CM9 not found"
}
```

### 500 Internal Server Error - 服务器错误

```json
{
  "detail": "Failed to generate follow-up suggestion: <error message>"
}
```

## 功能特性

### 1. 智能意图分析
- 自动分析用户行为日志
- 分类购买意图（高/中/低/犹豫）
- 基于多规则混合评分系统

### 2. 个性化消息生成
- 使用 LLM 生成个性化跟进消息
- 根据意图级别调整消息内容和语气
- 自动降级到规则消息（LLM 失败时）

### 3. 防打扰机制
- 低意图用户采用被动消息策略
- 避免过度打扰用户
- 保持友好但不过于主动

### 4. 建议动作映射
- **高意图** → 询问尺码推荐
- **中等意图** → 发送限时优惠券
- **犹豫** → 解释产品优势
- **低意图** → 被动友好消息

## 注意事项

1. **数据要求**: 确保数据库中已有用户行为日志数据
2. **LLM 配置**: 如果使用 LLM 生成消息，需要配置 `LLM_API_KEY` 和 `LLM_BASE_URL`
3. **性能**: LLM 调用可能需要 1-3 秒，建议在后台任务中执行
4. **降级机制**: 如果 LLM 不可用，会自动使用规则消息，确保服务可用性
5. **消息长度**: 生成的消息长度控制在 200 字符以内

## 相关文件

- `app/api/v1/followup.py` - API 端点实现
- `app/schemas/followup_schemas.py` - 请求/响应模型
- `app/services/followup_service.py` - 跟进建议服务
- `app/services/intent_engine.py` - 意图分析引擎
- `app/repositories/behavior_repository.py` - 行为数据仓库

## API 文档

启动服务后，可以访问 Swagger UI 查看完整的 API 文档：

```
http://127.0.0.1:8000/docs
```

在 Swagger UI 中可以直接测试接口，无需 Postman。

## 工作流程

1. **接收请求**: 获取 `user_id`、`sku` 和 `limit`
2. **验证商品**: 检查商品是否存在
3. **获取行为日志**: 从数据库查询用户行为记录
4. **构建行为摘要**: 计算访问次数、停留时间等统计信息
5. **分类意图**: 使用意图分析引擎确定购买意图级别
6. **生成建议**: 调用跟进建议服务生成个性化消息
7. **返回结果**: 返回建议动作和消息内容


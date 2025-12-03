# 意图分析 API 接口文档

## 概述

意图分析 API 是 V3 版本新增的功能，用于分析用户对特定商品的购买意图。该接口基于用户行为日志数据，通过多规则混合评分系统，智能判断用户的购买意图级别。

## 端点信息

- **URL**: `POST /ai/analyze/intent`
- **标签**: `ai`, `intent`
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
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "intent_level": "high",
  "reason": "用户已进入购买页面，这是强烈的购买信号。访问次数：2次，最大停留：25秒",
  "behavior_summary": {
    "visit_count": 2,
    "max_stay_seconds": 25,
    "avg_stay_seconds": 20.0,
    "total_stay_seconds": 40,
    "has_enter_buy_page": true,
    "has_favorite": false,
    "has_share": false,
    "has_click_size_chart": false,
    "event_types": ["browse", "enter_buy_page"],
    "event_type_counts": {
      "browse": 1,
      "enter_buy_page": 1
    }
  },
  "total_logs_analyzed": 2
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_id` | string | 用户ID |
| `sku` | string | 商品SKU |
| `intent_level` | string | 意图级别：`high`, `medium`, `low`, `hesitating` |
| `reason` | string | 意图级别的文本说明 |
| `behavior_summary` | object | 行为摘要数据（如果无行为记录则为 null） |
| `total_logs_analyzed` | integer | 分析的行为日志总数 |

### behavior_summary 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `visit_count` | integer | 访问次数 |
| `max_stay_seconds` | integer | 最大停留时间（秒） |
| `avg_stay_seconds` | float | 平均停留时间（秒） |
| `total_stay_seconds` | integer | 总停留时间（秒） |
| `has_enter_buy_page` | boolean | 是否进入购买页面 |
| `has_favorite` | boolean | 是否收藏商品 |
| `has_share` | boolean | 是否分享商品 |
| `has_click_size_chart` | boolean | 是否点击尺码表 |
| `event_types` | array[string] | 发生的事件类型列表 |
| `event_type_counts` | object | 各事件类型的计数 |

## 意图级别说明

### high (高意图)
用户有强烈的购买意向，应该优先跟进。

**典型特征**:
- 进入购买页面
- 最大停留时间 > 30 秒
- 访问 2 次以上且收藏了商品

### medium (中等意图)
用户有一定兴趣，可以适当跟进。

**典型特征**:
- 访问 2-3 次且平均停留 > 10 秒
- 单次访问但停留 > 15 秒或查看了尺码表

### low (低意图)
用户购买意向较低，可以暂缓跟进。

**典型特征**:
- 单次访问且停留 < 6 秒
- 单次访问且停留 < 15 秒且未收藏

### hesitating (犹豫)
用户多次访问但未采取行动，可能处于犹豫状态。

**典型特征**:
- 访问 3 次以上但未进入购买页且未收藏
- 访问 2 次以上但停留时间短且未采取行动

## Postman 测试指南

### 1. 创建请求

1. 打开 Postman
2. 创建新请求
3. 设置请求方法为 `POST`
4. 设置 URL: `http://127.0.0.1:8000/ai/analyze/intent`

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
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "intent_level": "high",
  "reason": "用户已进入购买页面，这是强烈的购买信号。访问次数：2次，最大停留：25秒",
  "behavior_summary": {
    "visit_count": 2,
    "max_stay_seconds": 25,
    "avg_stay_seconds": 20.0,
    "total_stay_seconds": 40,
    "has_enter_buy_page": true,
    "has_favorite": false,
    "has_share": false,
    "has_click_size_chart": false,
    "event_types": ["browse", "enter_buy_page"],
    "event_type_counts": {
      "browse": 1,
      "enter_buy_page": 1
    }
  },
  "total_logs_analyzed": 2
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
- `intent_level`: `"high"`
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
- `intent_level`: `"medium"` 或 `"high"`（取决于具体行为）

### 测试用例 3: 无行为记录

**请求**:
```json
{
  "user_id": "user_999",
  "sku": "8WZ01CM1",
  "limit": 50
}
```

**预期响应**:
- `intent_level`: `"low"`
- `reason`: `"无行为记录，无法分析购买意图"`
- `behavior_summary`: `null`
- `total_logs_analyzed`: `0`

### 测试用例 4: 自定义 limit

**请求**:
```json
{
  "user_id": "user_001",
  "sku": "8WZ01CM1",
  "limit": 10
}
```

**预期响应**:
- 只分析最近 10 条行为日志

## cURL 示例

```bash
curl -X POST "http://127.0.0.1:8000/ai/analyze/intent" \
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

url = "http://127.0.0.1:8000/ai/analyze/intent"
payload = {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "limit": 50
}

response = requests.post(url, json=payload)
data = response.json()

print(f"意图级别: {data['intent_level']}")
print(f"原因: {data['reason']}")
print(f"访问次数: {data['behavior_summary']['visit_count']}")
print(f"最大停留: {data['behavior_summary']['max_stay_seconds']}秒")
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

### 500 Internal Server Error - 服务器错误

```json
{
  "detail": "Failed to analyze intent: <error message>"
}
```

## 注意事项

1. **数据要求**: 确保数据库中已有用户行为日志数据
2. **性能**: 如果某个用户对某个商品的行为记录很多，建议设置合理的 `limit` 值
3. **时间范围**: 当前分析所有历史记录，按时间降序排列
4. **无数据情况**: 如果没有行为记录，会返回 `low` 意图级别，而不是错误

## 相关文件

- `app/api/v1/intent.py` - API 端点实现
- `app/schemas/intent_schemas.py` - 请求/响应模型
- `app/services/intent_engine.py` - 意图分析引擎
- `app/repositories/behavior_repository.py` - 行为数据仓库

## API 文档

启动服务后，可以访问 Swagger UI 查看完整的 API 文档：

```
http://127.0.0.1:8000/docs
```

在 Swagger UI 中可以直接测试接口，无需 Postman。


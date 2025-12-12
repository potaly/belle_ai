# Postman 调试指南 - 意图分析 API

## 基础配置

### API 端点
```
POST http://localhost:8000/ai/analyze/intent
```

### 请求头
```
Content-Type: application/json
```

### 默认端口
- 开发环境：`http://localhost:8000`
- 如果使用其他端口，请相应调整

---

## 测试用例

### 测试用例 1：HIGH 意图 - 进入购买页（最强信号）

**请求体：**
```json
{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "limit": 50
}
```

**预期响应：**
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

**说明：** 需要数据库中有 `user_001` 对 `8WZ01CM1` 的行为日志，且包含 `enter_buy_page` 事件。

---

### 测试用例 2：HIGH 意图 - 收藏 + 多次访问

**请求体：**
```json
{
    "user_id": "user_002",
    "sku": "8WZ01CM1",
    "limit": 50
}
```

**预期响应：**
```json
{
    "user_id": "user_002",
    "sku": "8WZ01CM1",
    "intent_level": "high",
    "reason": "用户访问 2 次并收藏了商品，表明持续兴趣和购买意向。平均停留：20.0秒",
    "behavior_summary": {
        "visit_count": 2,
        "max_stay_seconds": 25,
        "avg_stay_seconds": 20.0,
        "has_favorite": true,
        "has_enter_buy_page": false
    },
    "total_logs_analyzed": 2
}
```

**说明：** 需要数据库中有 `user_002` 对 `8WZ01CM1` 的 2 次以上访问记录，且包含 `favorite` 事件。

---

### 测试用例 3：HESITATING 意图 - 多次访问但无强信号

**请求体：**
```json
{
    "user_id": "user_003",
    "sku": "8WZ01CM1",
    "limit": 50
}
```

**预期响应：**
```json
{
    "user_id": "user_003",
    "sku": "8WZ01CM1",
    "intent_level": "hesitating",
    "reason": "用户已访问 3 次，平均停留 20.0 秒，但未采取购买相关行动（未进入购买页、未加购物车、未收藏），可能存在犹豫或需要更多信息。",
    "behavior_summary": {
        "visit_count": 3,
        "max_stay_seconds": 25,
        "avg_stay_seconds": 20.0,
        "has_enter_buy_page": false,
        "has_favorite": false,
        "has_add_to_cart": false
    },
    "total_logs_analyzed": 3
}
```

**说明：** 需要数据库中有 `user_003` 对 `8WZ01CM1` 的 3 次以上访问记录，但无 `enter_buy_page`、`favorite`、`add_to_cart` 等强信号。

---

### 测试用例 4：MEDIUM 意图 - 2次访问 + 一定停留时间

**请求体：**
```json
{
    "user_id": "user_004",
    "sku": "8WZ01CM1",
    "limit": 50
}
```

**预期响应：**
```json
{
    "user_id": "user_004",
    "sku": "8WZ01CM1",
    "intent_level": "medium",
    "reason": "用户访问 2 次，平均停留 18.0 秒，显示一定兴趣但尚未达到强烈购买意向。",
    "behavior_summary": {
        "visit_count": 2,
        "max_stay_seconds": 20,
        "avg_stay_seconds": 18.0,
        "has_enter_buy_page": false,
        "has_favorite": false
    },
    "total_logs_analyzed": 2
}
```

**说明：** 需要数据库中有 `user_004` 对 `8WZ01CM1` 的 2 次访问记录，平均停留时间 15 秒以上。

---

### 测试用例 5：LOW 意图 - 单次短暂访问

**请求体：**
```json
{
    "user_id": "user_005",
    "sku": "8WZ01CM1",
    "limit": 50
}
```

**预期响应：**
```json
{
    "user_id": "user_005",
    "sku": "8WZ01CM1",
    "intent_level": "low",
    "reason": "用户仅访问 1 次，停留时间仅 5 秒，购买意向较低。",
    "behavior_summary": {
        "visit_count": 1,
        "max_stay_seconds": 5,
        "avg_stay_seconds": 5.0,
        "has_enter_buy_page": false,
        "has_favorite": false
    },
    "total_logs_analyzed": 1
}
```

**说明：** 需要数据库中有 `user_005` 对 `8WZ01CM1` 的 1 次访问记录，停留时间 10 秒以下。

---

### 测试用例 6：无行为记录（边界情况）

**请求体：**
```json
{
    "user_id": "user_999",
    "sku": "8WZ01CM1",
    "limit": 50
}
```

**预期响应：**
```json
{
    "user_id": "user_999",
    "sku": "8WZ01CM1",
    "intent_level": "low",
    "reason": "无行为记录，无法分析购买意图",
    "behavior_summary": null,
    "total_logs_analyzed": 0
}
```

**说明：** 数据库中无该用户的行为记录，系统返回 `low` 意图。

---

## Postman 配置步骤

### 1. 创建新请求
- Method: `POST`
- URL: `http://localhost:8000/ai/analyze/intent`

### 2. 设置请求头
- Key: `Content-Type`
- Value: `application/json`

### 3. 设置请求体
- 选择 `Body` → `raw` → `JSON`
- 粘贴上述任一测试用例的请求体

### 4. 发送请求
点击 `Send` 按钮

---

## 快速测试脚本（Postman Collection）

### Collection JSON（可导入 Postman）

```json
{
    "info": {
        "name": "AI Smart Guide Service - Intent Analysis",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
    },
    "item": [
        {
            "name": "HIGH Intent - Enter Buy Page",
            "request": {
                "method": "POST",
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"user_id\": \"user_001\",\n    \"sku\": \"8WZ01CM1\",\n    \"limit\": 50\n}"
                },
                "url": {
                    "raw": "http://localhost:8000/ai/analyze/intent",
                    "protocol": "http",
                    "host": ["localhost"],
                    "port": "8000",
                    "path": ["ai", "analyze", "intent"]
                }
            }
        },
        {
            "name": "HESITATING Intent - Multiple Visits No Action",
            "request": {
                "method": "POST",
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"user_id\": \"user_003\",\n    \"sku\": \"8WZ01CM1\",\n    \"limit\": 50\n}"
                },
                "url": {
                    "raw": "http://localhost:8000/ai/analyze/intent",
                    "protocol": "http",
                    "host": ["localhost"],
                    "port": "8000",
                    "path": ["ai", "analyze", "intent"]
                }
            }
        },
        {
            "name": "LOW Intent - Single Short Visit",
            "request": {
                "method": "POST",
                "header": [
                    {
                        "key": "Content-Type",
                        "value": "application/json"
                    }
                ],
                "body": {
                    "mode": "raw",
                    "raw": "{\n    \"user_id\": \"user_005\",\n    \"sku\": \"8WZ01CM1\",\n    \"limit\": 50\n}"
                },
                "url": {
                    "raw": "http://localhost:8000/ai/analyze/intent",
                    "protocol": "http",
                    "host": ["localhost"],
                    "port": "8000",
                    "path": ["ai", "analyze", "intent"]
                }
            }
        }
    ]
}
```

---

## 其他相关 API

### AI 智能销售 Agent API（推荐）
```
POST http://localhost:8000/ai/agent/sales_flow
```

**请求体：**
```json
{
    "user_id": "user_001",
    "guide_id": "guide_001",
    "sku": "8WZ01CM1"
}
```

### 销售流程图 API
```
POST http://localhost:8000/ai/sales/graph
```

**请求体：**
```json
{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "guide_id": "guide_001",
    "use_custom_plan": true
}
```

### 跟进建议 API
```
POST http://localhost:8000/ai/followup/suggest
```

**请求体：**
```json
{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "guide_id": "guide_001"
}
```

---

## 注意事项

1. **数据库准备**：确保数据库中有对应的用户行为日志数据
2. **服务启动**：确保 FastAPI 服务已启动（`uvicorn app.main:app --reload`）
3. **端口检查**：确认服务运行在 `8000` 端口（或相应调整 URL）
4. **数据格式**：请求体必须是有效的 JSON 格式
5. **字段验证**：
   - `user_id` 和 `sku` 为必填字段
   - `limit` 可选，默认 50，范围 1-100

---

## 常见错误

### 404 Not Found
- 检查 URL 是否正确
- 确认服务已启动

### 422 Unprocessable Entity
- 检查请求体 JSON 格式是否正确
- 确认必填字段已提供

### 500 Internal Server Error
- 检查数据库连接
- 查看服务日志

---

## 调试技巧

1. **查看 Swagger 文档**：访问 `http://localhost:8000/docs` 查看完整 API 文档
2. **查看日志**：服务端会输出详细的执行日志
3. **使用 Postman Console**：查看请求和响应的详细信息
4. **测试不同场景**：使用不同的 `user_id` 和 `sku` 组合测试


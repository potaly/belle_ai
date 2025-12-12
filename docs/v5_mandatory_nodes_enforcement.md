# V5.0.0: 强制业务节点保护机制

## 问题背景

在 V4 版本中，当 `use_custom_plan=true` 时，系统可能绕过关键的业务步骤：
- 意图判断（`intent_level`）
- 防打扰决策（`anti_disturb`）

这会导致：
- 返回结果缺失核心字段（`intent_level` 为 `None`）
- 导购/前端无法信任系统输出
- 业务逻辑不可控

## 解决方案

### 1. 强制节点定义

在 `app/agents/planner_agent.py` 中定义了强制节点列表：

```python
# 强制业务节点（在任何执行模式下都不能跳过）
MANDATORY_NODES = [
    "fetch_product",
    "fetch_behavior_summary",
    "classify_intent",
    "anti_disturb_check",
]

# 可选节点（可以根据业务规则跳过）
OPTIONAL_NODES = [
    "retrieve_rag",
    "generate_copy",
    "generate_followup",
]
```

### 2. `build_final_plan()` 函数

新增函数确保强制节点始终被包含在最终执行计划中：

- **输入**：自定义计划（可能缺少强制节点）
- **输出**：最终计划（包含所有强制节点，按依赖顺序排列）
- **逻辑**：
  - 自动注入所有强制节点
  - 保留自定义计划中的可选节点
  - 按依赖顺序排列（强制节点在前，可选节点在后）
  - 去重（保持第一次出现的顺序）

### 3. 执行后验证

在 `app/agents/graph/sales_graph.py` 中添加了 `_validate_mandatory_fields()` 函数：

- 验证 `intent_level` 不为 `None`（如果有 `user_id` 和 `behavior_summary`）
- 验证 `allowed` / `anti_disturb_blocked` 存在（如果执行了反打扰检查）
- 如果验证失败，抛出 `BusinessLogicError`（包含 `error_code` 和详细消息）

### 4. API 响应增强

#### 新增字段

1. **`decision_reason`** (string)
   - 决策原因的文本说明
   - 包含意图级别说明和反打扰决策说明
   - 用于可解释性

2. **`plan_used`** (List[str])
   - 实际执行的节点列表（数组格式）
   - 始终包含所有强制节点
   - 用于调试和审计

#### 更新位置

- `app/api/v1/agent_sales_flow.py`：主 Agent API
- `app/api/v1/sales_graph.py`：销售图 API
- `app/schemas/agent_sales_flow_schemas.py`：响应 schema
- `app/schemas/sales_graph_schemas.py`：响应 schema

### 5. 错误处理

新增 `BusinessLogicError` 异常类：

```python
class BusinessLogicError(Exception):
    """业务逻辑错误：当强制业务步骤未执行或结果不完整时抛出。"""
    
    def __init__(self, message: str, error_code: str = "MISSING_MANDATORY_FIELD"):
        self.message = message
        self.error_code = error_code
```

API 返回格式：

```json
{
    "error": "Business logic validation failed",
    "error_code": "MISSING_INTENT_LEVEL",
    "message": "Mandatory field 'intent_level' is missing after graph execution..."
}
```

## 使用示例

### 场景 1：自定义计划缺少强制节点

**输入**：
```json
{
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "use_custom_plan": true
}
```

**自定义计划**（由 planner 生成，可能缺少某些节点）：
```python
["retrieve_rag", "generate_copy"]  # 缺少强制节点
```

**最终计划**（自动注入强制节点）：
```python
[
    "fetch_product",           # 自动注入
    "fetch_behavior_summary",  # 自动注入
    "classify_intent",         # 自动注入
    "anti_disturb_check",      # 自动注入
    "retrieve_rag",            # 保留
    "generate_copy"             # 保留
]
```

### 场景 2：执行后验证失败

如果执行后 `intent_level` 仍为 `None`（例如节点执行失败），系统会抛出 `BusinessLogicError`：

```json
{
    "error": "Business logic validation failed",
    "error_code": "MISSING_INTENT_LEVEL",
    "message": "Mandatory field 'intent_level' is missing after graph execution..."
}
```

### 场景 3：响应包含决策原因

**响应**：
```json
{
    "success": true,
    "data": {
        "intent": {
            "level": "high",
            "reason": "用户已进入购买页面，这是强烈的购买信号。"
        },
        "allowed": true,
        "anti_disturb_blocked": false,
        "decision_reason": "用户意图级别为 high：用户已进入购买页面，这是强烈的购买信号。；反打扰检查通过，允许主动接触",
        "plan_used": [
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

## 测试

测试文件：`tests/test_mandatory_nodes.py`

### 测试用例

1. **`test_build_final_plan_injects_mandatory_nodes`**
   - 验证：自定义计划缺少强制节点时，会自动注入

2. **`test_build_final_plan_preserves_existing_mandatory_nodes`**
   - 验证：如果自定义计划已包含强制节点，不会重复添加

3. **`test_build_final_plan_handles_empty_custom_plan`**
   - 验证：空的自定义计划会生成完整的强制节点计划

4. **`test_build_final_plan_skips_nodes_when_context_has_data`**
   - 验证：如果上下文已有数据，会跳过对应的节点

5. **`test_decision_reason_generation`**
   - 验证：决策原因生成逻辑正确

6. **`test_decision_reason_for_blocked_case`**
   - 验证：被阻止时的决策原因包含正确信息

## 架构改进

### 之前的问题

```
自定义计划 → 直接执行 → 可能缺少强制节点 → 返回结果不完整
```

### 现在的流程

```
自定义计划 → build_final_plan() → 注入强制节点 → 执行 → 验证 → 返回完整结果
```

## 关键原则

1. **业务正确性优先**：强制节点绝不能跳过
2. **可解释性**：所有决策都有 `decision_reason`
3. **可追溯性**：`plan_used` 记录实际执行的节点
4. **失败安全**：验证失败时抛出明确的错误

## 向后兼容性

- 现有 API 调用不受影响
- 新增字段为可选（但强制节点保护始终启用）
- `plan_used` 从字符串改为数组（更规范）

## 后续优化建议

1. **LLM 驱动的规划器**：在保持强制节点保护的前提下，允许 LLM 决定可选节点的顺序
2. **更细粒度的验证**：根据上下文判断哪些强制节点真正需要执行
3. **性能优化**：缓存已执行的节点结果，避免重复执行


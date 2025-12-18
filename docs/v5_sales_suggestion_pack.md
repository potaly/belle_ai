# V5.4.0: 导购可执行建议包

## 业务背景

当前 Sales Graph 已具备：
- ✅ intent_level / intent_reason（可解释）
- ✅ anti_disturb_check（可控）
- ✅ RAG 防串货（安全，可为空）
- ✅ copy 生成（但仅返回 final_message）

**实际业务问题：**
导购只拿到一句 `final_message`，价值有限：
- ❌ 不知道"为什么现在找这位顾客"
- ❌ 不知道"该采取什么动作"（尺码/优惠/库存/顾虑消除）
- ❌ 没有备选话术，导购不敢发
- ❌ 没有置信度/建议强度，导购无法判断是否值得打扰

**V5.4.0 目标：**
将输出从"一句话"升级为"导购可执行建议包"：
1. 给出 `recommended_action`（动作类型）
2. 给出 `why_now`（时机解释）
3. 给出 `send_recommendation`（建议发/不建议发 + 置信度）
4. 给出 2~3 条候选话术（primary + alternatives）
5. 保持生产可控：不夸张、不串货、可解释、可回溯

## 核心改进

### 1. 新增输出结构

```json
{
  "sales_suggestion": {
    "intent_level": "high",
    "confidence": "high",
    "why_now": "用户已访问 3 次，表现出持续关注；用户已收藏商品",
    "recommended_action": "ask_size",
    "action_explanation": "用户已查看尺码表，建议主动询问尺码以推进购买",
    "message_pack": [
      {
        "type": "primary",
        "strategy": "主动推进",
        "message": "这款黑色运动鞋很舒适，您平时穿什么码？"
      },
      {
        "type": "alternative",
        "strategy": "主动推进",
        "message": "黑色运动鞋适合日常运动，您觉得怎么样？"
      }
    ],
    "send_recommendation": {
      "suggested": true,
      "note": "用户购买意图明确，建议主动联系",
      "risk_level": "low"
    }
  },
  "final_message": "这款黑色运动鞋很舒适，您平时穿什么码？"  // 向后兼容
}
```

### 2. 推荐动作类型

| Action | 说明 | 适用场景 |
|--------|------|---------|
| `ask_size` | 询问尺码 | 高意图 + 查看尺码表 |
| `reassure_comfort` | 强调舒适度 | 犹豫意图，消除顾虑 |
| `mention_stock` | 提醒库存 | 高意图 + 已收藏 |
| `mention_promo` | 提及优惠 | 有促销活动时 |
| `scene_recommendation` | 场景推荐 | 中等意图 |
| `soft_check_in` | 轻量提醒 | 低意图，不施压 |

### 3. 消息包生成规则

1. **数量**：2~3 条消息（1 条 primary + 1~2 条 alternatives）
2. **行动建议**：每条消息必须包含一个轻量行动建议（根据 `recommended_action`）
3. **顾客上下文**：自然引用行为摘要（如"我看你最近看了几次..."）
4. **禁止词汇**：禁止使用营销词汇（太香了/必入/闭眼冲等）
5. **事实基础**：基于商品事实，不串货
6. **长度限制**：默认 ≤ 45 字符（可配置）

### 4. 降级机制

- **LLM 失败**：自动使用规则模板
- **输出验证失败**：自动使用规则模板
- **降级保证**：至少返回 2 条消息（primary + alternative）

## 技术实现

### 文件结构

```
app/services/
└── sales_suggestion_service.py  # 建议包生成服务（NEW）

app/schemas/
└── sales_graph_schemas.py       # 添加 SalesSuggestionSchema（UPDATED）

app/api/v1/
└── sales_graph.py                # 集成建议包生成（UPDATED）

tests/
└── test_sales_suggestion.py      # 测试覆盖（NEW）
```

### 核心函数

#### `build_suggestion_pack(context) -> SalesSuggestion`
构建导购可执行建议包：
1. 选择推荐动作（`choose_recommended_action`）
2. 构建时机解释（`build_why_now`）
3. 计算置信度（`calculate_confidence`）
4. 生成消息包（`generate_message_pack`）
5. 构建发送建议（`build_send_recommendation`）

#### `choose_recommended_action(intent_level, behavior_summary, product) -> tuple[str, str]`
根据意图级别和行为特征选择推荐动作。

#### `generate_message_pack(...) -> List[MessageItem]`
生成消息包（2~3条候选话术）：
- 尝试使用 LLM 生成多条消息
- 验证每条消息（长度、禁止词汇、行动建议）
- LLM 失败时使用规则模板

### 配置

使用现有配置：
- `copy_max_length: int = 45`（消息最大长度）

## 使用示例

### API 响应

```json
{
  "success": true,
  "message": "Sales graph executed successfully",
  "data": {
    "user_id": "user_001",
    "sku": "8WZ01CM1",
    "intent_level": "high",
    "allowed": true,
    "sales_suggestion": {
      "intent_level": "high",
      "confidence": "high",
      "why_now": "用户已访问 3 次，表现出持续关注；用户已收藏商品",
      "recommended_action": "ask_size",
      "action_explanation": "用户已查看尺码表，建议主动询问尺码以推进购买",
      "message_pack": [
        {
          "type": "primary",
          "strategy": "主动推进",
          "message": "这款黑色运动鞋很舒适，您平时穿什么码？"
        },
        {
          "type": "alternative",
          "strategy": "主动推进",
          "message": "黑色运动鞋适合日常运动，您觉得怎么样？"
        }
      ],
      "send_recommendation": {
        "suggested": true,
        "note": "用户购买意图明确，建议主动联系",
        "risk_level": "low"
      }
    },
    "final_message": "这款黑色运动鞋很舒适，您平时穿什么码？"
  }
}
```

## 测试覆盖

测试文件：`tests/test_sales_suggestion.py`

### 测试用例

1. **推荐动作选择测试**
   - ✅ 高意图 + 查看尺码表 → `ask_size`
   - ✅ 高意图 + 已收藏 → `mention_stock`
   - ✅ 犹豫意图 + 多次访问 → `reassure_comfort`
   - ✅ 中等意图 + 有场景 → `scene_recommendation`
   - ✅ 低意图 → `soft_check_in`
   - ✅ 所有动作在允许集合中

2. **置信度计算测试**
   - ✅ 高意图 → `high`
   - ✅ 犹豫意图 → `medium` 或 `high`
   - ✅ 中等意图 → `medium`
   - ✅ 低意图 → `low`
   - ✅ 收藏/进入购买页提升置信度
   - ✅ 多次访问提升置信度

3. **建议包生成测试**
   - ✅ 所有 intent_level 的建议包生成
   - ✅ `message_pack` 长度 >= 2
   - ✅ 每条消息包含行动建议关键词
   - ✅ 禁止词汇检测
   - ✅ 长度约束（≤ 45 字符）

4. **降级测试**
   - ✅ LLM 失败时使用规则模板
   - ✅ 降级后仍返回 2 条消息
   - ✅ 降级消息符合业务规则

5. **向后兼容测试**
   - ✅ `final_message` 等于 primary message
   - ✅ 旧客户端仍可正常使用

## 业务验收标准

### ✅ MUST PASS

1. **推荐动作**
   - `recommended_action` 在允许集合中
   - `action_explanation` 清晰说明原因

2. **时机解释**
   - `why_now` 可读性强，导购能理解
   - 基于意图原因和行为摘要

3. **消息包**
   - 至少 2 条消息（primary + alternative）
   - 每条消息包含行动建议关键词
   - 不包含禁止词汇
   - 长度符合约束

4. **发送建议**
   - `suggested` 明确（true/false）
   - `risk_level` 合理（low/medium/high）
   - `note` 提供操作建议

5. **向后兼容**
   - `final_message` 存在且等于 primary message
   - 旧客户端不受影响

## 向后兼容

- ✅ 保留 `final_message` 字段（等于 primary message）
- ✅ 新增 `sales_suggestion` 字段（可选，新客户端使用）
- ✅ 如果建议包生成失败，不影响原有功能

## 未来优化方向

1. **个性化策略**
   - 根据用户历史偏好调整动作
   - 根据商品类型优化话术

2. **A/B 测试**
   - 不同动作的转化率对比
   - 不同话术的效果评估

3. **多轮对话**
   - 根据顾客回复调整策略
   - 支持上下文记忆

4. **实时反馈**
   - 导购反馈机制
   - 持续优化建议质量


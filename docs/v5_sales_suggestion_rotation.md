# V5.6.0: 导购可用性持续改造 - 策略多样与确定性轮换

## 业务背景

目前 `/ai/sales/graph` 的输出已经具备 `sales_suggestion`，但导购实际可用性仍偏低：
- ❌ `message_pack` 多次请求内容相同或只是裁剪，导购感知"没用"
- ❌ 文案更像商品标题改写，缺少对用户行为的回应
- ❌ `strategy` 字段偏内部语言（"消除顾虑"），导购不知道下一步怎么做
- ❌ 缺少"最佳发送时机""风险提示""下一步动作"

**V5.6.0 目标**：
1. `message_pack` 变成"策略多样"，不是"句子多样"
2. 文案必须"回应行为"（例如：多次浏览/停留长→轻咨询）
3. 引入"可控多样性"：同一用户同一商品在同一时间窗口内稳定，但跨天/跨窗口可轮换
4. 输出增加导购可执行字段：`recommended_action`（动作化）、`best_timing`、`risk_note`、`next_step`
5. 保持生产特性：可解释、可回放、可测试、可审计

## 核心改进

### 1. 策略多样性（非句子多样性）

**之前**：
- 消息包中的消息只是同一策略的不同表述
- 导购感知"没用"

**现在**：
- 消息包至少 3 条消息，策略必须不同
- 每条消息使用不同策略（询问顾虑 / 询问尺码 / 场景推荐 / 舒适度保证 / 轻量提醒）
- 策略描述动作化（"询问顾虑"而非"消除顾虑"）

### 2. 行为感知消息

**之前**：
- 文案更像商品标题改写
- 缺少对用户行为的回应

**现在**：
- 主消息必须自然引用顾客行为
- 例如："我看你最近看了几次..."、"刚刚浏览挺久..."
- 基于行为摘要（访问次数、停留时间等）

### 3. 确定性轮换（非随机）

**核心概念**：
- 同一用户同一商品在同一时间窗口内 → 相同的 `message_pack`（稳定）
- 不同窗口 → 轮换策略顺序和变体（多样）
- 完全可重现（用于调试）

**实现**：
- 使用 `rotation_key = hash(user_id + sku + rotation_window)`
- 默认 6 小时窗口，也可使用日窗口
- 基于轮换键选择策略和变体

### 4. 动作化推荐动作

**新的推荐动作枚举**：
- `ask_concern_type` - 询问顾虑类型（尺码/舒适度/场景）
- `ask_size` - 尺码咨询
- `reassure_comfort` - 舒适度保证
- `scene_relate` - 场景关联
- `mention_promo` - 提及优惠（仅当有优惠时）
- `mention_stock` - 库存提醒（仅当已验证时）
- `soft_check_in` - 轻量提醒

### 5. 操作指导字段

**新增字段**：
- `best_timing` - 最佳发送时机（"now" / "within 30 minutes" / "tonight 19-21"）
- `next_step` - 下一步动作（用户回复后导购该做什么）
- `risk_level` - 风险等级（已有，保持不变）
- `note` - 操作建议（已有，保持不变）

## 技术实现

### 文件结构

```
app/services/
├── strategy_rotation.py          # 确定性轮换逻辑（NEW）
├── message_validators.py          # 消息验证器（NEW）
├── fallback_message_pack.py      # 降级消息包生成（NEW）
└── sales_suggestion_service.py   # 集成新逻辑（UPDATED）

app/schemas/
└── sales_graph_schemas.py         # 添加新字段（UPDATED）

tests/
└── test_sales_suggestion_rotation.py  # 测试覆盖（NEW）
```

### 核心函数

#### `get_rotation_window(timestamp, window_hours) -> str`
获取轮换窗口标识符：
- 默认 6 小时窗口
- 可选 24 小时（日窗口）
- 格式：`YYYY-MM-DD-HH` 或 `YYYY-MM-DD`

#### `compute_rotation_key(user_id, sku, rotation_window) -> int`
计算轮换键（确定性哈希）：
- 相同 (user_id, sku, window) → 相同键
- 不同窗口 → 不同键
- 完全可重现

#### `select_strategies_for_pack(intent_level, recommended_action, rotation_key, min_count) -> List[Tuple]`
为消息包选择策略（确定性轮换）：
- 至少 `min_count` 个策略（默认 3）
- 策略必须不同（无重复）
- 基于 `recommended_action` 和 `intent_level`
- 使用 `rotation_key` 进行确定性轮换

#### `validate_message_pack(message_pack, current_sku, max_length, min_count) -> Tuple[bool, Optional[str]]`
验证消息包：
- 至少 `min_count` 条消息
- 策略必须不同（无重复）
- 备选消息不能是主消息的截断版本
- 每条消息通过单条验证

#### `generate_fallback_message_pack(...) -> List[dict]`
使用规则模板生成降级消息包：
- 支持确定性轮换
- 确保策略多样性
- 行为感知消息生成

## 使用示例

### API 响应（V5.6.0+）

```json
{
  "sales_suggestion": {
    "intent_level": "hesitating",
    "confidence": "medium",
    "why_now": "用户已访问 4 次，表现出持续关注；用户停留时间较长",
    "recommended_action": "ask_concern_type",
    "action_explanation": "用户多次访问但未下单，可能存在顾虑，建议询问顾虑类型",
    "message_pack": [
      {
        "type": "primary",
        "strategy": "询问顾虑",
        "message": "我看你最近看了几次，有什么顾虑吗？"
      },
      {
        "type": "alternative",
        "strategy": "询问尺码",
        "message": "您平时穿什么码？"
      },
      {
        "type": "alternative",
        "strategy": "舒适度保证",
        "message": "这款很舒适，不用担心脚感"
      }
    ],
    "send_recommendation": {
      "suggested": true,
      "best_timing": "within 30 minutes",
      "note": "用户有一定兴趣，可以尝试联系",
      "risk_level": "low",
      "next_step": "根据用户顾虑类型，提供针对性解答"
    }
  }
}
```

## 测试覆盖

测试文件：`tests/test_sales_suggestion_rotation.py`

### 测试用例

1. **确定性轮换测试**
   - ✅ 同一 (user_id, sku) 在同一窗口内 → 相同的 `message_pack`
   - ✅ 不同窗口 → `message_pack` 至少有一条消息或策略顺序不同

2. **消息包质量测试**
   - ✅ `message_pack` 有 >= 3 条消息且 >= 3 个不同策略
   - ✅ hesitating 主消息引用行为上下文
   - ✅ 禁止词汇不存在
   - ✅ 备选消息不是主消息的子串截断

3. **降级测试**
   - ✅ LLM 失败时使用降级模板
   - ✅ 降级后仍返回有效包（至少 3 条消息，策略多样）

4. **策略选择测试**
   - ✅ 不同意图级别选择不同策略
   - ✅ 策略选择基于 `recommended_action`

5. **消息验证测试**
   - ✅ 消息包验证要求策略多样性
   - ✅ 重复策略的包验证失败

## 业务验收标准

### ✅ MUST PASS

1. **策略多样性**
   - `message_pack` 长度 >= 3
   - 策略必须不同（无重复）
   - 备选消息不是主消息的截断版本

2. **行为感知**
   - 主消息必须引用顾客行为（如"我看你最近看了几次..."）
   - 基于行为摘要自然生成

3. **确定性轮换**
   - 同一窗口内稳定
   - 跨窗口可轮换
   - 完全可重现

4. **操作指导**
   - `best_timing` 明确（"now" / "within 30 minutes" / "tonight 19-21"）
   - `next_step` 清晰（用户回复后导购该做什么）
   - `recommended_action` 动作化（"ask_concern_type" 而非"消除顾虑"）

5. **安全性和合规性**
   - 禁止词汇检查通过
   - 跨 SKU 泄漏检查通过
   - 长度约束通过
   - 行动建议关键词检查通过

## 向后兼容

- ✅ 保留现有字段（`intent_level`、`confidence`、`why_now` 等）
- ✅ 新增字段（`best_timing`、`next_step`）有默认值
- ✅ 旧客户端仍可正常使用（忽略新字段）

## 未来优化方向

1. **缓存优化**
   - 使用 Redis 缓存计算好的建议包（窗口 TTL）
   - 减少成本，确保窗口内输出一致

2. **个性化策略**
   - 根据用户历史偏好调整策略
   - 根据商品类型优化策略选择

3. **A/B 测试**
   - 不同策略的转化率对比
   - 持续优化策略选择

4. **实时反馈**
   - 导购反馈机制
   - 持续优化消息质量


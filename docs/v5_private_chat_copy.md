# V5.3.0: 导购 1v1 私聊促单话术生成

## 业务背景

当前系统在 P1~P3 已完成：
- ✅ 强制业务闭环（intent / anti-disturb 不可跳过）
- ✅ 意图等级已稳定输出（high / hesitating / medium / low）
- ✅ RAG 已完成防串货与事实落地（可能为空，属正常）

但之前生成的文案偏"营销广告"，在真实导购私聊场景中存在风险：
- ❌ 导购不敢直接发送
- ❌ 语气不自然
- ❌ 行动引导不清晰

**V5.3.0 目标：将文案生成升级为"导购 1v1 私聊促单话术"，可直接发送给真实顾客，且在生产环境中安全可控。**

## 核心改进

### 1. 语气升级
- **之前**：营销广告风格（"太香了"、"必入"、"闭眼冲"）
- **现在**：自然亲切，像朋友聊天

### 2. 策略化生成
根据 `intent_level` 使用不同策略：

| Intent Level | 策略 | 行动建议 |
|-------------|------|---------|
| `high` | 主动推进 | 询问尺码、提醒库存、提及促销 |
| `hesitating` | 消除顾虑 | 轻量提问、场景推荐、舒适度保证 |
| `medium` | 场景化推荐 | 场景建议、搭配建议、轻量询问 |
| `low` | 轻量提醒 | 克制语气，不施压，不强烈行动号召 |

### 3. 严格约束
- **长度限制**：默认 ≤ 45 个中文字符（可配置）
- **禁止词汇**：禁止使用"太香了"、"必入"、"闭眼冲"、"爆款"、"秒杀"等营销词汇
- **事实约束**：所有信息必须来自商品数据，禁止编造

### 4. 降级机制
- **LLM 失败**：自动使用规则模板
- **输出验证失败**：自动使用规则模板
- **降级模板**：确定性、安全可控

## 技术实现

### 文件结构

```
app/services/
├── prompt_templates.py      # 提示词模板（系统提示词 + 用户提示词）
├── fallback_copy.py         # 规则驱动的降级文案生成
└── copy_service.py          # 文案生成服务（集成 LLM + 降级）

app/agents/tools/
└── copy_tool.py             # Agent 工具（使用新逻辑）

app/core/
└── config.py                # 配置（添加 copy_max_length）

tests/
└── test_private_chat_copy.py  # 测试覆盖
```

### 核心函数

#### `build_system_prompt() -> str`
构建系统提示词，定义：
- 角色：真实门店导购
- 禁止：营销词汇、夸大宣传、强推、编造事实
- 要求：自然、亲切、适度引导

#### `build_user_prompt(product, intent_level, intent_reason, ...) -> str`
构建用户提示词，包含：
- 商品信息（唯一事实来源）
- 顾客意图分析（intent_level + intent_reason + behavior_summary）
- 策略建议（根据 intent_level）
- 输出要求（长度、语气、行动建议）

#### `generate_fallback_copy(product, intent_level, max_length) -> str`
规则驱动的降级文案生成：
- 基于商品事实，不编造
- 根据 intent_level 使用不同模板
- 确保输出安全可控

#### `validate_copy_output(copy_text, max_length) -> tuple[bool, Optional[str]]`
验证生成的文案：
- 长度检查
- 禁止词汇检查
- 非空检查

### 配置

在 `app/core/config.py` 中添加：

```python
copy_max_length: int = 45  # 最大长度（字符）
```

可通过环境变量 `COPY_MAX_LENGTH` 配置。

## 使用示例

### 在 Agent 系统中使用

```python
from app.agents.tools.copy_tool import generate_marketing_copy

# context 必须包含：
# - context.product (商品信息)
# - context.intent_level (意图级别)
# - context.extra["intent_reason"] (意图原因，可选)
# - context.behavior_summary (行为摘要，可选)

context = await generate_marketing_copy(context)
copy_text = context.messages[-1]["content"]
```

### 在 API 中使用

```python
from app.services.copy_service import generate_private_chat_copy

copy, llm_used, strategy = await generate_private_chat_copy(
    db=db,
    sku="8WZ01CM1",
    intent_level="high",
    intent_reason="用户多次访问并收藏",
    behavior_summary={"visit_count": 3, "has_favorite": True},
)
```

## 测试覆盖

测试文件：`tests/test_private_chat_copy.py`

### 测试用例

1. **提示词模板测试**
   - ✅ 系统提示词生成
   - ✅ 用户提示词生成（所有 intent_level）
   - ✅ 输出验证（长度、禁止词汇、非空）

2. **降级模板测试**
   - ✅ 所有 intent_level 的降级模板
   - ✅ 长度约束
   - ✅ 禁止词汇检查
   - ✅ 行动建议关键词

3. **集成测试**
   - ✅ LLM 成功场景
   - ✅ LLM 失败降级
   - ✅ 输出验证失败降级

4. **业务规则测试**
   - ✅ 高意图包含行动建议
   - ✅ 犹豫意图包含提问
   - ✅ 中等意图包含场景推荐
   - ✅ 低意图不包含强烈行动号召

## 业务验收标准

### ✅ MUST PASS

1. **输出适合 1v1 私聊**
   - 语气自然、非营销
   - 可直接发送给真实顾客

2. **包含行动建议**
   - 每个输出至少包含一个轻量行动建议
   - 根据 intent_level 使用不同策略

3. **长度约束**
   - 默认 ≤ 45 字符（可配置）
   - 降级模板也遵守长度限制

4. **低意图克制**
   - `intent_level == low` 时，语气克制
   - 不包含强烈的行动号召

5. **禁止营销词汇**
   - 不包含"太香了"、"必入"、"闭眼冲"等
   - LLM 输出验证失败时自动降级

6. **降级机制**
   - LLM 失败时使用规则模板
   - 输出验证失败时使用规则模板
   - 降级输出确定性、安全可控

## 向后兼容

- ✅ 保留 `prepare_copy_generation()` 函数（legacy API）
- ✅ 旧的 API 端点（`/ai/generate/copy`）继续工作
- ✅ Agent 系统自动使用新逻辑

## 配置说明

### 环境变量

```bash
# 文案最大长度（字符）
COPY_MAX_LENGTH=45
```

### 代码配置

```python
from app.core.config import get_settings

settings = get_settings()
max_length = settings.copy_max_length  # 默认 45
```

## 未来优化方向

1. **个性化策略**
   - 根据用户历史行为调整策略
   - 根据商品类型调整话术风格

2. **A/B 测试**
   - 不同策略的效果对比
   - 优化行动建议的转化率

3. **多轮对话**
   - 支持上下文记忆
   - 根据顾客回复调整策略


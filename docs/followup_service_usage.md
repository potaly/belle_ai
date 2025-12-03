# 跟进建议服务使用文档

## 概述

跟进建议服务（Follow-up Suggestion Service）是 V3 版本的核心功能之一，用于根据用户的购买意图和行为数据，生成个性化的跟进建议和消息。

## 功能特性

- **混合规则 + LLM**: 结合规则引擎和 LLM 生成个性化消息
- **意图级别驱动**: 根据意图级别（high/medium/low/hesitating）选择不同的跟进策略
- **智能降级**: LLM 失败时自动降级到基于规则的备用消息
- **防打扰机制**: 低意图用户采用被动友好消息，避免过度打扰

## 核心函数

### `generate_followup_suggestion`

```python
async def generate_followup_suggestion(
    product: Product,
    summary: dict,
    intention_level: str,
) -> dict:
```

**参数**:
- `product`: Product 实例（商品信息）
- `summary`: 行为摘要字典（来自意图分析）
- `intention_level`: 意图级别字符串（"high", "medium", "low", "hesitating"）

**返回值**:
```python
{
    "suggested_action": str,  # 建议动作类型
    "message": str            # 个性化跟进消息
}
```

## 建议动作类型

### `ask_size` - 询问尺码推荐
- **触发条件**: 意图级别 = `high`
- **适用场景**: 用户有强烈购买意向，可能只需要尺码建议
- **消息示例**: "您好！看到您对这款舒适跑鞋很感兴趣，需要我帮您推荐合适的尺码吗？"

### `send_coupon` - 发送限时优惠券
- **触发条件**: 意图级别 = `medium`
- **适用场景**: 用户有一定兴趣，通过优惠券促进转化
- **消息示例**: "您好！为您准备了限时优惠券，购买舒适跑鞋可享受特别优惠，数量有限，先到先得！"

### `explain_benefits` - 解释产品优势
- **触发条件**: 意图级别 = `hesitating`
- **适用场景**: 用户多次访问但未采取行动，需要温和推动
- **消息示例**: "您好！舒适跑鞋具有舒适、时尚等特点，非常适合您。如有任何疑问，欢迎随时咨询！"

### `passive_message` - 被动友好消息
- **触发条件**: 意图级别 = `low`
- **适用场景**: 用户购买意向较低，发送被动消息保持联系但不打扰
- **消息示例**: "您好！舒适跑鞋正在热销中，如有需要欢迎随时联系我们。"

### `do_not_disturb` - 不打扰
- **触发条件**: 意图级别 = `low`（可选）
- **适用场景**: 完全不打扰用户，或发送极被动的消息
- **消息示例**: "您好！舒适跑鞋已为您保留，如有需要欢迎随时联系我们。"

## 使用示例

### 基本用法

```python
from app.services.followup_service import generate_followup_suggestion
from app.models.product import Product
from app.services.intent_engine import classify_intent

# 1. 获取商品信息
product = get_product_by_sku(db, "8WZ01CM1")

# 2. 获取行为摘要和意图级别
summary = {
    "visit_count": 2,
    "max_stay_seconds": 30,
    "avg_stay_seconds": 20.0,
    "has_enter_buy_page": True,
    "has_favorite": False,
    ...
}
intention_level, reason = classify_intent(summary)

# 3. 生成跟进建议
result = await generate_followup_suggestion(
    product=product,
    summary=summary,
    intention_level=intention_level,
)

# 4. 使用结果
print(f"建议动作: {result['suggested_action']}")
print(f"消息内容: {result['message']}")
```

### 完整流程示例

```python
import asyncio
from app.repositories.behavior_repository import get_recent_behavior
from app.repositories.product_repository import get_product_by_sku
from app.services.intent_engine import classify_intent
from app.services.followup_service import generate_followup_suggestion

async def generate_followup_for_user(db, user_id: str, sku: str):
    """为指定用户生成跟进建议"""
    
    # 1. 获取商品
    product = get_product_by_sku(db, sku)
    if not product:
        return None
    
    # 2. 获取行为日志
    logs = await get_recent_behavior(db, user_id, sku, limit=50)
    
    # 3. 构建行为摘要
    if not logs:
        summary = {
            "visit_count": 0,
            "max_stay_seconds": 0,
            "avg_stay_seconds": 0.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "has_share": False,
            "has_click_size_chart": False,
            "event_types": [],
        }
        intention_level = "low"
    else:
        # 计算统计数据
        stay_seconds_list = [log.stay_seconds for log in logs]
        max_stay_seconds = max(stay_seconds_list) if stay_seconds_list else 0
        total_stay_seconds = sum(stay_seconds_list)
        avg_stay_seconds = total_stay_seconds / len(logs) if logs else 0.0
        
        event_types = [log.event_type for log in logs]
        
        summary = {
            "visit_count": len(logs),
            "max_stay_seconds": max_stay_seconds,
            "avg_stay_seconds": round(avg_stay_seconds, 2),
            "total_stay_seconds": total_stay_seconds,
            "has_enter_buy_page": "enter_buy_page" in event_types,
            "has_favorite": "favorite" in event_types,
            "has_share": "share" in event_types,
            "has_click_size_chart": "click_size_chart" in event_types,
            "event_types": list(set(event_types)),
        }
        
        # 4. 分类意图
        intention_level, reason = classify_intent(summary)
    
    # 5. 生成跟进建议
    result = await generate_followup_suggestion(
        product=product,
        summary=summary,
        intention_level=intention_level,
    )
    
    return result

# 使用
result = asyncio.run(generate_followup_for_user(db, "user_001", "8WZ01CM1"))
print(result)
```

## LLM 集成

### Prompt 构建

LLM prompt 包含以下信息：
1. **商品信息**: 名称、SKU、价格、标签、描述
2. **行为摘要**: 访问次数、停留时间、关键行为
3. **意图级别**: 高/中/低/犹豫
4. **建议动作**: 询问尺码/发送优惠券/解释优势/被动消息

### 系统提示词

```
你是一个专业的鞋类销售顾问，擅长根据用户的购买意图和行为数据，
生成个性化、友好、不打扰的跟进消息。你的消息应该：
1. 简洁明了（不超过50字）
2. 针对性强（根据意图级别和用户行为）
3. 友好自然（不要过于推销）
4. 提供价值（帮助用户做决定）
```

### 降级机制

如果 LLM 调用失败（网络错误、超时、API 错误等），服务会自动降级到基于规则的备用消息生成器，确保服务始终可用。

## 测试

运行测试脚本：

```bash
python test_followup_service.py
```

测试脚本会：
1. 从数据库加载真实的商品和行为数据
2. 测试不同意图级别的跟进建议生成
3. 验证 LLM 和规则降级机制
4. 输出 JSON 格式的响应示例

## 注意事项

1. **异步函数**: `generate_followup_suggestion` 是异步函数，必须在 `async` 上下文中调用
2. **LLM 配置**: 确保环境变量中配置了 `LLM_API_KEY` 和 `LLM_BASE_URL`
3. **消息长度**: LLM 生成的消息会被限制在 200 字符以内
4. **性能**: LLM 调用可能需要 1-3 秒，建议在后台任务中执行
5. **错误处理**: 服务会自动处理 LLM 失败，降级到规则消息

## 相关文件

- `app/services/followup_service.py` - 跟进建议服务实现
- `app/services/intent_engine.py` - 意图分析引擎
- `app/services/llm_client.py` - LLM 客户端
- `app/repositories/behavior_repository.py` - 行为数据仓库
- `test_followup_service.py` - 测试脚本

## API 集成

跟进建议服务可以轻松集成到 API 端点中：

```python
@router.post("/ai/followup/suggest")
async def suggest_followup(
    request: FollowupRequest,
    db: Session = Depends(get_db),
) -> FollowupResponse:
    """生成跟进建议"""
    # 1. 获取商品和行为数据
    # 2. 分析意图
    # 3. 生成跟进建议
    # 4. 返回结果
    pass
```

## 未来优化

- [ ] 支持多语言消息生成
- [ ] 添加消息模板库
- [ ] 支持 A/B 测试不同的消息策略
- [ ] 集成反打扰机制（避免频繁打扰同一用户）
- [ ] 添加消息效果追踪和分析


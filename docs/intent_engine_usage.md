# 意图分析引擎使用文档

## 概述

`intent_engine.py` 是 V3 版本新增的用户购买意图分析引擎，基于用户行为日志数据，通过多规则混合评分系统，智能判断用户的购买意图级别。

## 文件位置

- **代码文件**: `app/services/intent_engine.py`
- **测试文件**: `test_intent_engine.py`

## 功能说明

### 主要函数

#### `classify_intent`

根据用户行为摘要，分类用户的购买意图级别。

**函数签名**:
```python
def classify_intent(summary: Dict) -> Tuple[str, str]
```

**参数说明**:
- `summary` (Dict): 用户行为摘要字典，包含以下字段：
  - `visit_count` (int): 访问次数
  - `max_stay_seconds` (int): 最大停留时间（秒）
  - `avg_stay_seconds` (float): 平均停留时间（秒）
  - `total_stay_seconds` (int): 总停留时间（秒）
  - `has_enter_buy_page` (bool): 是否进入购买页面
  - `has_favorite` (bool): 是否收藏商品
  - `has_share` (bool): 是否分享商品
  - `has_click_size_chart` (bool): 是否点击尺码表
  - `event_types` (List[str]): 发生的事件类型列表
  - `first_visit_time` (datetime, optional): 首次访问时间
  - `last_visit_time` (datetime, optional): 最后访问时间

**返回值**:
- `Tuple[str, str]`: (intention_level, reason)
  - `intention_level`: 意图级别，取值为 `"high"`, `"medium"`, `"low"`, `"hesitating"` 之一
  - `reason`: 文本说明，解释为什么选择这个意图级别

## 意图级别说明

### 1. **high** (高意图)
用户有强烈的购买意向，应该优先跟进。

**触发条件**（满足任一即可）：
- 用户已进入购买页面（`has_enter_buy_page = True`）
- 最大停留时间 > 30 秒（`max_stay_seconds > 30`）
- 访问 2 次以上且收藏了商品（`visit_count >= 2 AND has_favorite = True`）

**示例**:
```python
summary = {
    "visit_count": 2,
    "max_stay_seconds": 35,
    "avg_stay_seconds": 25.0,
    "has_enter_buy_page": True,
    "has_favorite": False,
}
level, reason = classify_intent(summary)
# level = "high"
# reason = "用户已进入购买页面，这是强烈的购买信号。访问次数：2次，最大停留：35秒"
```

### 2. **medium** (中等意图)
用户有一定兴趣，可以适当跟进。

**触发条件**：
- 访问 2-3 次且平均停留 > 10 秒
- 单次访问但停留 > 15 秒或查看了尺码表

**示例**:
```python
summary = {
    "visit_count": 2,
    "max_stay_seconds": 18,
    "avg_stay_seconds": 12.0,
    "has_enter_buy_page": False,
    "has_favorite": False,
}
level, reason = classify_intent(summary)
# level = "medium"
# reason = "用户访问 2 次，平均停留 12.0 秒，显示一定兴趣但尚未达到强烈购买意向"
```

### 3. **low** (低意图)
用户购买意向较低，可以暂缓跟进。

**触发条件**：
- 单次访问且停留 < 6 秒
- 单次访问且停留 < 15 秒且未收藏

**示例**:
```python
summary = {
    "visit_count": 1,
    "max_stay_seconds": 4,
    "avg_stay_seconds": 4.0,
    "has_enter_buy_page": False,
    "has_favorite": False,
}
level, reason = classify_intent(summary)
# level = "low"
# reason = "用户仅访问 1 次，停留时间仅 4 秒，购买意向较低"
```

### 4. **hesitating** (犹豫)
用户多次访问但未采取行动，可能处于犹豫状态，需要更多信息或引导。

**触发条件**：
- 访问 3 次以上但未进入购买页且未收藏
- 访问 2 次以上但停留时间短且未采取行动

**示例**:
```python
summary = {
    "visit_count": 4,
    "max_stay_seconds": 15,
    "avg_stay_seconds": 10.0,
    "has_enter_buy_page": False,
    "has_favorite": False,
}
level, reason = classify_intent(summary)
# level = "hesitating"
# reason = "用户已访问 4 次，但未采取购买相关行动（未进入购买页、未收藏），可能存在犹豫或需要更多信息。平均停留：10.0秒"
```

## 评分系统

引擎使用多规则混合评分系统，计算以下维度：

1. **高意图信号** (high_intent_signals)
   - 进入购买页: +50 分
   - 收藏商品: +30 分
   - 分享商品: +20 分
   - 查看尺码表: +15 分

2. **参与深度** (engagement_depth)
   - 最大停留 > 30 秒: +40 分
   - 最大停留 > 15 秒: +20 分
   - 最大停留 > 6 秒: +10 分
   - 平均停留 > 20 秒: +20 分
   - 平均停留 > 10 秒: +10 分

3. **访问频率** (visit_frequency)
   - 访问 3 次以上: +30 分
   - 访问 2 次: +15 分
   - 访问 1 次: +5 分

4. **犹豫信号** (hesitation_signals)
   - 多次访问但无行动: +30 分
   - 多次快速访问无行动: +20 分

**综合评分** = 高意图信号 + 参与深度 + 访问频率 - 犹豫信号

## 使用示例

### 基础用法

```python
from app.services.intent_engine import classify_intent

# 构建行为摘要
summary = {
    "visit_count": 3,
    "max_stay_seconds": 45,
    "avg_stay_seconds": 25.0,
    "total_stay_seconds": 75,
    "has_enter_buy_page": True,
    "has_favorite": True,
    "has_share": False,
    "has_click_size_chart": True,
    "event_types": ["browse", "enter_buy_page", "favorite", "click_size_chart"],
}

# 分类意图
intent_level, reason = classify_intent(summary)

print(f"意图级别: {intent_level}")
print(f"原因: {reason}")
# 输出:
# 意图级别: high
# 原因: 用户已进入购买页面，这是强烈的购买信号。访问次数：3次，最大停留：45秒
```

### 从行为日志生成摘要

```python
from app.repositories.behavior_repository import get_recent_behavior
from app.services.intent_engine import classify_intent
from app.core.database import SessionLocal

async def analyze_user_intent(user_id: str, sku: str):
    """分析用户购买意图"""
    db = SessionLocal()
    try:
        # 获取最近行为日志
        logs = await get_recent_behavior(db, user_id, sku, limit=50)
        
        if not logs:
            return "low", "无行为记录"
        
        # 生成行为摘要
        summary = {
            "visit_count": len(logs),
            "max_stay_seconds": max(log.stay_seconds for log in logs),
            "avg_stay_seconds": sum(log.stay_seconds for log in logs) / len(logs),
            "total_stay_seconds": sum(log.stay_seconds for log in logs),
            "has_enter_buy_page": any(log.event_type == "enter_buy_page" for log in logs),
            "has_favorite": any(log.event_type == "favorite" for log in logs),
            "has_share": any(log.event_type == "share" for log in logs),
            "has_click_size_chart": any(log.event_type == "click_size_chart" for log in logs),
            "event_types": [log.event_type for log in logs],
        }
        
        # 分类意图
        intent_level, reason = classify_intent(summary)
        
        return intent_level, reason
    finally:
        db.close()
```

### 在 FastAPI 中使用

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.behavior_repository import get_recent_behavior
from app.services.intent_engine import classify_intent

router = APIRouter()

@router.get("/user/{user_id}/product/{sku}/intent")
async def get_user_intent(
    user_id: str,
    sku: str,
    db: Session = Depends(get_db)
):
    """获取用户购买意图分析"""
    # 获取行为日志
    logs = await get_recent_behavior(db, user_id, sku, limit=50)
    
    if not logs:
        return {
            "intent_level": "low",
            "reason": "无行为记录",
            "summary": {}
        }
    
    # 生成摘要
    summary = {
        "visit_count": len(logs),
        "max_stay_seconds": max(log.stay_seconds for log in logs),
        "avg_stay_seconds": sum(log.stay_seconds for log in logs) / len(logs),
        "total_stay_seconds": sum(log.stay_seconds for log in logs),
        "has_enter_buy_page": any(log.event_type == "enter_buy_page" for log in logs),
        "has_favorite": any(log.event_type == "favorite" for log in logs),
        "has_share": any(log.event_type == "share" for log in logs),
        "has_click_size_chart": any(log.event_type == "click_size_chart" for log in logs),
        "event_types": list(set(log.event_type for log in logs)),
    }
    
    # 分类意图
    intent_level, reason = classify_intent(summary)
    
    return {
        "intent_level": intent_level,
        "reason": reason,
        "summary": summary
    }
```

## 规则优先级

意图分类按照以下优先级顺序判断：

1. **高意图规则**（最高优先级）
   - 进入购买页 → `high`
   - 最大停留 > 30 秒 → `high`
   - 访问 2+ 次且收藏 → `high`

2. **犹豫规则**
   - 访问 3+ 次但无行动 → `hesitating`
   - 访问 2+ 次但停留短且无行动 → `hesitating`

3. **中等意图规则**
   - 访问 2-3 次且平均停留 > 10 秒 → `medium`
   - 单次访问但停留 > 15 秒或查看尺码表 → `medium`

4. **低意图规则**
   - 单次访问 < 6 秒 → `low`
   - 单次访问 < 15 秒且未收藏 → `low`

5. **综合评分规则**（兜底）
   - 如果以上规则都不匹配，使用综合评分判断

## 测试

运行测试脚本验证功能：

```bash
python test_intent_engine.py
```

测试脚本包含 8 个测试用例，覆盖所有意图级别和边界情况。

## 扩展性

代码设计考虑了未来的 LLM 优化：

1. **规则系统**: 当前使用规则引擎，可以轻松添加新规则
2. **评分系统**: 评分权重可以调整，也可以替换为机器学习模型
3. **可维护性**: 代码结构清晰，函数职责单一，便于扩展

未来可以：
- 使用 LLM 对边界情况进行更精细的判断
- 基于历史数据训练机器学习模型
- 结合更多特征（如商品价格、用户历史购买等）

## 注意事项

1. **数据质量**: 确保行为摘要数据准确，特别是停留时间和事件类型
2. **时间窗口**: 当前分析所有历史记录，未来可以考虑只分析最近 N 天的行为
3. **阈值调整**: 评分阈值可以根据实际业务数据调整
4. **性能**: 函数是同步的，如果需要在异步环境中使用，可以使用 `run_in_executor`

## 相关文件

- `app/repositories/behavior_repository.py` - 行为数据仓库
- `app/models/user_behavior_log.py` - 行为日志模型
- `test_intent_engine.py` - 测试脚本

## V3 版本规划

意图分析引擎是 V3 版本的核心组件，将用于：

1. **智能跟进建议**: 根据意图级别生成不同的跟进策略
2. **防打扰机制**: 避免对低意图用户过度联系
3. **个性化推荐**: 根据意图级别推荐合适的商品或优惠


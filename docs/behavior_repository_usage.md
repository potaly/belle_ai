# 用户行为仓库使用文档

## 概述

`behavior_repository.py` 是 V3 版本新增的用户行为数据访问层，用于从 MySQL 数据库中查询和分析用户行为日志。该仓库提供了获取用户对特定商品的最近行为记录的功能。

## 文件位置

- **代码文件**: `app/repositories/behavior_repository.py`
- **模型文件**: `app/models/user_behavior_log.py`
- **测试文件**: `test_behavior_repository.py`

## 功能说明

### 主要函数

#### `get_recent_behavior`

获取指定用户对指定商品的最近行为日志。

**函数签名**:
```python
async def get_recent_behavior(
    db: Session,
    user_id: str,
    sku: str,
    limit: int = 50,
) -> List[UserBehaviorLog]
```

**参数说明**:
- `db` (Session): 数据库会话对象
- `user_id` (str): 用户ID，用于过滤行为日志
- `sku` (str): 商品SKU，用于过滤行为日志
- `limit` (int): 返回的最大记录数，默认 50 条

**返回值**:
- `List[UserBehaviorLog]`: 用户行为日志列表，按 `occurred_at` 降序排列（最新的在前）

**异常**:
- 如果数据库查询出错，会记录错误日志并重新抛出异常

## 支持的事件类型

用户行为日志支持以下事件类型：

- `browse` - 浏览商品
- `enter_buy_page` - 进入购买页面
- `click_size_chart` - 点击尺码表
- `favorite` - 收藏商品
- `share` - 分享商品

## 使用示例

### 基础用法

```python
from app.core.database import SessionLocal
from app.repositories.behavior_repository import get_recent_behavior

# 创建数据库会话
db = SessionLocal()

try:
    # 查询用户对商品的最近行为
    logs = await get_recent_behavior(
        db=db,
        user_id="user_001",
        sku="8WZ01CM1",
        limit=10
    )
    
    # 处理结果
    for log in logs:
        print(f"[{log.occurred_at}] {log.event_type} - 停留 {log.stay_seconds}秒")
        
finally:
    db.close()
```

### 在 FastAPI 中使用

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.repositories.behavior_repository import get_recent_behavior

router = APIRouter()

@router.get("/user/{user_id}/product/{sku}/behavior")
async def get_user_product_behavior(
    user_id: str,
    sku: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """获取用户对商品的最近行为日志"""
    logs = await get_recent_behavior(db, user_id, sku, limit)
    return {
        "user_id": user_id,
        "sku": sku,
        "total": len(logs),
        "logs": [
            {
                "event_type": log.event_type,
                "stay_seconds": log.stay_seconds,
                "occurred_at": log.occurred_at.isoformat()
            }
            for log in logs
        ]
    }
```

### 分析用户行为模式

```python
async def analyze_user_behavior(user_id: str, sku: str, db: Session):
    """分析用户行为模式"""
    logs = await get_recent_behavior(db, user_id, sku, limit=50)
    
    if not logs:
        return {"message": "无行为记录"}
    
    # 统计事件类型
    event_counts = {}
    total_stay_time = 0
    
    for log in logs:
        event_type = log.event_type
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        total_stay_time += log.stay_seconds
    
    # 计算平均停留时间
    avg_stay_time = total_stay_time / len(logs) if logs else 0
    
    # 检查是否有高意图事件
    high_intent_events = ['enter_buy_page', 'favorite', 'share']
    has_high_intent = any(log.event_type in high_intent_events for log in logs)
    
    return {
        "total_events": len(logs),
        "event_distribution": event_counts,
        "avg_stay_time": round(avg_stay_time, 2),
        "has_high_intent": has_high_intent,
        "first_interaction": logs[-1].occurred_at.isoformat() if logs else None,
        "last_interaction": logs[0].occurred_at.isoformat() if logs else None,
    }
```

## 数据库表结构

### user_behavior_logs 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 日志主键ID |
| user_id | VARCHAR(64) | 用户ID |
| guide_id | VARCHAR(64) | 导购ID |
| sku | VARCHAR(64) | 商品SKU |
| event_type | VARCHAR(32) | 事件类型 |
| stay_seconds | INT | 停留时长（秒） |
| occurred_at | DATETIME | 事件发生时间 |

### 索引

- `idx_ubl_user_sku`: (user_id, sku, occurred_at) - 用于快速查询用户对商品的最近行为
- `idx_ubl_event_time`: (event_type, occurred_at) - 用于按事件类型和时间查询

## 性能考虑

1. **索引优化**: 查询使用了 `idx_ubl_user_sku` 复合索引，可以快速定位用户对特定商品的行为记录
2. **排序**: 使用 `ORDER BY occurred_at DESC` 排序，索引支持此排序操作
3. **限制结果**: 默认限制 50 条记录，避免返回过多数据
4. **异步支持**: 函数定义为 `async`，可以在异步上下文中使用

## 日志记录

函数会记录以下日志：

- **INFO**: 查询开始和结果统计
- **DEBUG**: 事件类型分布和时间范围
- **ERROR**: 数据库查询错误（包含完整堆栈）

## 错误处理

- 如果数据库连接失败，会抛出异常
- 如果查询出错，会记录错误日志并重新抛出异常
- 如果未找到记录，返回空列表（不会抛出异常）

## 测试

运行测试脚本验证功能：

```bash
python test_behavior_repository.py
```

测试脚本会验证：
1. 正常查询存在的用户和商品
2. 查询不存在的用户（返回空列表）
3. 查询不存在的商品（返回空列表）
4. limit 参数的正确性
5. 不同事件类型的支持

## 注意事项

1. **数据库会话管理**: 确保在使用后关闭数据库会话，避免连接泄漏
2. **异步函数**: 虽然函数定义为 `async`，但内部使用的是同步的 SQLAlchemy 查询。如果需要在真正的异步环境中使用，可以考虑使用 `run_in_executor` 或异步 SQLAlchemy
3. **数据量**: 如果某个用户对某个商品的行为记录非常多，建议设置合理的 `limit` 值
4. **时间范围**: 函数返回的是所有历史记录（按时间降序），如果需要时间范围过滤，可以在调用后自行过滤

## 相关文件

- `app/models/user_behavior_log.py` - 用户行为日志 ORM 模型
- `app/core/database.py` - 数据库配置和会话管理
- `sql/schema.sql` - 数据库表结构定义
- `sql/seed_data.sql` - 测试数据

## V3 版本规划

该仓库是 V3 版本用户行为分析功能的基础，后续将用于：

1. **用户意图分析**: 基于行为日志分析用户购买意图
2. **智能跟进建议**: 根据行为模式生成跟进建议
3. **防打扰机制**: 避免过度联系用户


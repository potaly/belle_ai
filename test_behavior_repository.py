"""测试用户行为仓库功能"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import SessionLocal
from app.repositories.behavior_repository import get_recent_behavior

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_get_recent_behavior():
    """测试获取最近行为日志"""
    print("\n" + "=" * 80)
    print("测试：用户行为仓库 - get_recent_behavior")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        # 测试用例 1: 查询存在的用户和商品
        print("\n【测试用例 1】查询存在的用户和商品")
        print("-" * 80)
        user_id = "user_001"
        sku = "8WZ01CM1"
        limit = 10
        
        print(f"参数:")
        print(f"  - user_id: {user_id}")
        print(f"  - sku: {sku}")
        print(f"  - limit: {limit}")
        
        try:
            logs = await get_recent_behavior(db, user_id, sku, limit)
            
            print(f"\n结果: 找到 {len(logs)} 条行为日志")
            
            if logs:
                print(f"\n前 {min(5, len(logs))} 条记录:")
                for i, log in enumerate(logs[:5], 1):
                    print(f"  {i}. [{log.occurred_at}] {log.event_type} - "
                          f"停留 {log.stay_seconds}秒")
                
                # 统计事件类型
                event_types = {}
                for log in logs:
                    event_types[log.event_type] = event_types.get(log.event_type, 0) + 1
                
                print(f"\n事件类型统计:")
                for event_type, count in sorted(event_types.items()):
                    print(f"  - {event_type}: {count} 次")
                
                # 验证排序（应该按时间降序）
                is_sorted = all(
                    logs[i].occurred_at >= logs[i+1].occurred_at
                    for i in range(len(logs) - 1)
                )
                print(f"\n排序验证: {'✓ 按时间降序排列' if is_sorted else '✗ 排序错误'}")
            else:
                print("  (未找到行为日志)")
                
        except Exception as e:
            print(f"  ✗ 错误: {e}")
            logger.error(f"测试失败: {e}", exc_info=True)
        
        # 测试用例 2: 查询不存在的用户
        print("\n【测试用例 2】查询不存在的用户")
        print("-" * 80)
        user_id = "user_999"
        sku = "8WZ01CM1"
        
        print(f"参数:")
        print(f"  - user_id: {user_id} (不存在)")
        print(f"  - sku: {sku}")
        
        try:
            logs = await get_recent_behavior(db, user_id, sku, limit=10)
            print(f"\n结果: 找到 {len(logs)} 条行为日志")
            if len(logs) == 0:
                print("  ✓ 正确返回空列表（用户不存在）")
            else:
                print("  ⚠️ 警告：应该返回空列表")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
        
        # 测试用例 3: 查询不存在的商品
        print("\n【测试用例 3】查询不存在的商品")
        print("-" * 80)
        user_id = "user_001"
        sku = "INVALID_SKU"
        
        print(f"参数:")
        print(f"  - user_id: {user_id}")
        print(f"  - sku: {sku} (不存在)")
        
        try:
            logs = await get_recent_behavior(db, user_id, sku, limit=10)
            print(f"\n结果: 找到 {len(logs)} 条行为日志")
            if len(logs) == 0:
                print("  ✓ 正确返回空列表（商品不存在）")
            else:
                print("  ⚠️ 警告：应该返回空列表")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
        
        # 测试用例 4: 测试 limit 参数
        print("\n【测试用例 4】测试 limit 参数")
        print("-" * 80)
        user_id = "user_001"
        sku = "8WZ01CM1"
        limit = 5
        
        print(f"参数:")
        print(f"  - user_id: {user_id}")
        print(f"  - sku: {sku}")
        print(f"  - limit: {limit}")
        
        try:
            logs = await get_recent_behavior(db, user_id, sku, limit=limit)
            print(f"\n结果: 找到 {len(logs)} 条行为日志")
            if len(logs) <= limit:
                print(f"  ✓ 正确限制结果数量（≤ {limit}）")
            else:
                print(f"  ✗ 错误：返回了 {len(logs)} 条，超过限制 {limit}")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
        
        # 测试用例 5: 测试不同的事件类型
        print("\n【测试用例 5】查看不同事件类型")
        print("-" * 80)
        user_id = "user_003"
        sku = "8WZ03CM3"
        
        print(f"参数:")
        print(f"  - user_id: {user_id}")
        print(f"  - sku: {sku}")
        
        try:
            logs = await get_recent_behavior(db, user_id, sku, limit=20)
            print(f"\n结果: 找到 {len(logs)} 条行为日志")
            
            if logs:
                event_types = set(log.event_type for log in logs)
                print(f"\n包含的事件类型: {sorted(event_types)}")
                
                # 验证支持的事件类型
                supported_events = {'browse', 'enter_buy_page', 'click_size_chart', 'favorite', 'share'}
                found_events = event_types & supported_events
                print(f"\n支持的事件类型: {sorted(supported_events)}")
                print(f"找到的事件类型: {sorted(found_events)}")
                
                if found_events:
                    print("  ✓ 找到支持的事件类型")
                else:
                    print("  ⚠️ 未找到支持的事件类型（可能是数据问题）")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
        
        print("\n" + "=" * 80)
        print("测试完成")
        print("=" * 80)
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_get_recent_behavior())


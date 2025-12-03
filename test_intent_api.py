"""Test script for intent analysis API."""
import asyncio
import json
import sys

from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.repositories.behavior_repository import get_recent_behavior
from app.services.intent_engine import classify_intent


async def test_intent_analysis():
    """Test intent analysis with real data."""
    print("=" * 80)
    print("测试意图分析功能")
    print("=" * 80)
    
    # Test cases
    test_cases = [
        {
            "user_id": "user_001",
            "sku": "8WZ01CM1",
            "description": "用户1，商品1",
        },
        {
            "user_id": "user_002",
            "sku": "8WZ02CM2",
            "description": "用户2，商品2",
        },
        {
            "user_id": "user_999",
            "sku": "8WZ01CM1",
            "description": "不存在的用户（测试无数据情况）",
        },
    ]
    
    db: Session = SessionLocal()
    
    try:
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[测试用例 {i}] {test_case['description']}")
            print("-" * 80)
            
            user_id = test_case["user_id"]
            sku = test_case["sku"]
            
            # Get behavior logs
            logs = await get_recent_behavior(db, user_id, sku, limit=50)
            
            if not logs:
                print(f"  ✗ 无行为记录 (user_id={user_id}, sku={sku})")
                print(f"  预期意图级别: low")
                print(f"  预期原因: 无行为记录，无法分析购买意图")
                continue
            
            print(f"  ✓ 找到 {len(logs)} 条行为记录")
            
            # Build summary
            stay_seconds_list = [log.stay_seconds for log in logs]
            max_stay_seconds = max(stay_seconds_list) if stay_seconds_list else 0
            total_stay_seconds = sum(stay_seconds_list)
            avg_stay_seconds = total_stay_seconds / len(logs) if logs else 0.0
            
            event_types = [log.event_type for log in logs]
            has_enter_buy_page = "enter_buy_page" in event_types
            has_favorite = "favorite" in event_types
            has_share = "share" in event_types
            has_click_size_chart = "click_size_chart" in event_types
            
            summary_dict = {
                "visit_count": len(logs),
                "max_stay_seconds": max_stay_seconds,
                "avg_stay_seconds": round(avg_stay_seconds, 2),
                "total_stay_seconds": total_stay_seconds,
                "has_enter_buy_page": has_enter_buy_page,
                "has_favorite": has_favorite,
                "has_share": has_share,
                "has_click_size_chart": has_click_size_chart,
                "event_types": list(set(event_types)),
            }
            
            print(f"  行为摘要:")
            print(f"    - 访问次数: {summary_dict['visit_count']}")
            print(f"    - 最大停留: {summary_dict['max_stay_seconds']}秒")
            print(f"    - 平均停留: {summary_dict['avg_stay_seconds']:.1f}秒")
            print(f"    - 进入购买页: {has_enter_buy_page}")
            print(f"    - 收藏: {has_favorite}")
            print(f"    - 分享: {has_share}")
            print(f"    - 查看尺码表: {has_click_size_chart}")
            print(f"    - 事件类型: {summary_dict['event_types']}")
            
            # Classify intent
            intent_level, reason = classify_intent(summary_dict)
            
            print(f"\n  意图分析结果:")
            print(f"    - 意图级别: {intent_level}")
            print(f"    - 原因: {reason}")
            
            # Print JSON format (for Postman reference)
            print(f"\n  API 请求示例 (JSON):")
            request_json = {
                "user_id": user_id,
                "sku": sku,
                "limit": 50,
            }
            print(json.dumps(request_json, ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f"\n✗ 测试失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)
    print("\n提示: 使用 Postman 测试 API:")
    print("  POST http://127.0.0.1:8000/ai/analyze/intent")
    print("  Body (JSON):")
    print('  {')
    print('    "user_id": "user_001",')
    print('    "sku": "8WZ01CM1",')
    print('    "limit": 50')
    print('  }')


if __name__ == "__main__":
    asyncio.run(test_intent_analysis())


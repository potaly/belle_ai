"""Test script for follow-up suggestion service."""
import asyncio
import json
import sys

from sqlalchemy.orm import Session

# Add project root to path
sys.path.insert(0, ".")

from app.core.database import SessionLocal
from app.models.product import Product
from app.repositories.product_repository import get_product_by_sku
from app.services.followup_service import generate_followup_suggestion
from app.services.intent_engine import classify_intent
from app.repositories.behavior_repository import get_recent_behavior


async def test_followup_suggestion():
    """Test follow-up suggestion generation."""
    print("=" * 80)
    print("测试跟进建议服务")
    print("=" * 80)
    
    db: Session = SessionLocal()
    
    try:
        # Test cases with different intent levels
        test_cases = [
            {
                "user_id": "user_001",
                "sku": "8WZ01CM1",
                "description": "用户1，商品1（测试高意图）",
            },
            {
                "user_id": "user_002",
                "sku": "8WZ02CM2",
                "description": "用户2，商品2（测试中等意图）",
            },
            {
                "user_id": "user_003",
                "sku": "8WZ03CM3",
                "description": "用户3，商品3（测试高意图-进入购买页）",
            },
        ]
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n[测试用例 {i}] {test_case['description']}")
            print("-" * 80)
            
            user_id = test_case["user_id"]
            sku = test_case["sku"]
            
            # Step 1: Get product
            product = get_product_by_sku(db, sku)
            if not product:
                print(f"  ✗ 商品不存在: sku={sku}")
                continue
            
            print(f"  ✓ 商品: {product.name} (SKU: {product.sku})")
            
            # Step 2: Get behavior logs and classify intent
            logs = await get_recent_behavior(db, user_id, sku, limit=50)
            
            if not logs:
                print(f"  ✗ 无行为记录，使用默认低意图")
                summary = {
                    "visit_count": 0,
                    "max_stay_seconds": 0,
                    "avg_stay_seconds": 0.0,
                    "total_stay_seconds": 0,
                    "has_enter_buy_page": False,
                    "has_favorite": False,
                    "has_share": False,
                    "has_click_size_chart": False,
                    "event_types": [],
                }
                intention_level = "low"
            else:
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
                
                summary = {
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
                
                # Classify intent
                intention_level, reason = classify_intent(summary)
                print(f"  ✓ 意图级别: {intention_level}")
                print(f"  ✓ 原因: {reason}")
            
            # Step 3: Generate follow-up suggestion
            print(f"\n  生成跟进建议...")
            result = await generate_followup_suggestion(
                product=product,
                summary=summary,
                intention_level=intention_level,
            )
            
            print(f"\n  跟进建议结果:")
            print(f"    - 建议动作: {result['suggested_action']}")
            print(f"    - 消息内容: {result['message']}")
            
            # Print JSON format (for API reference)
            print(f"\n  API 响应示例 (JSON):")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
    except Exception as e:
        print(f"\n✗ 测试失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(test_followup_suggestion())


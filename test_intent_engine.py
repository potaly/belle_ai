"""测试意图分析引擎功能"""
from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from app.services.intent_engine import classify_intent


def test_intent_classification():
    """测试意图分类功能"""
    print("\n" + "=" * 80)
    print("测试：意图分析引擎 - classify_intent")
    print("=" * 80)
    
    # 测试用例 1: HIGH INTENT - 进入购买页
    print("\n【测试用例 1】高意图 - 进入购买页")
    print("-" * 80)
    summary1 = {
        "visit_count": 2,
        "max_stay_seconds": 25,
        "avg_stay_seconds": 20.0,
        "total_stay_seconds": 40,
        "has_enter_buy_page": True,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse", "enter_buy_page"],
    }
    level1, reason1 = classify_intent(summary1)
    print(f"结果: {level1}")
    print(f"原因: {reason1}")
    assert level1 == "high", f"预期 'high'，实际 '{level1}'"
    print("  ✓ 测试通过")
    
    # 测试用例 2: HIGH INTENT - 长停留时间
    print("\n【测试用例 2】高意图 - 长停留时间")
    print("-" * 80)
    summary2 = {
        "visit_count": 1,
        "max_stay_seconds": 45,
        "avg_stay_seconds": 45.0,
        "total_stay_seconds": 45,
        "has_enter_buy_page": False,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse"],
    }
    level2, reason2 = classify_intent(summary2)
    print(f"结果: {level2}")
    print(f"原因: {reason2}")
    assert level2 == "high", f"预期 'high'，实际 '{level2}'"
    print("  ✓ 测试通过")
    
    # 测试用例 3: HIGH INTENT - 多次访问 + 收藏
    print("\n【测试用例 3】高意图 - 多次访问并收藏")
    print("-" * 80)
    summary3 = {
        "visit_count": 3,
        "max_stay_seconds": 20,
        "avg_stay_seconds": 15.0,
        "total_stay_seconds": 45,
        "has_enter_buy_page": False,
        "has_favorite": True,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse", "favorite"],
    }
    level3, reason3 = classify_intent(summary3)
    print(f"结果: {level3}")
    print(f"原因: {reason3}")
    assert level3 == "high", f"预期 'high'，实际 '{level3}'"
    print("  ✓ 测试通过")
    
    # 测试用例 4: HESITATING - 多次访问但无行动
    print("\n【测试用例 4】犹豫 - 多次访问但无行动")
    print("-" * 80)
    summary4 = {
        "visit_count": 4,
        "max_stay_seconds": 15,
        "avg_stay_seconds": 10.0,
        "total_stay_seconds": 40,
        "has_enter_buy_page": False,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse"],
    }
    level4, reason4 = classify_intent(summary4)
    print(f"结果: {level4}")
    print(f"原因: {reason4}")
    assert level4 == "hesitating", f"预期 'hesitating'，实际 '{level4}'"
    print("  ✓ 测试通过")
    
    # 测试用例 5: MEDIUM INTENT - 2-3次访问，平均停留>10秒
    print("\n【测试用例 5】中等意图 - 2-3次访问，平均停留>10秒")
    print("-" * 80)
    summary5 = {
        "visit_count": 2,
        "max_stay_seconds": 18,
        "avg_stay_seconds": 12.0,
        "total_stay_seconds": 24,
        "has_enter_buy_page": False,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse"],
    }
    level5, reason5 = classify_intent(summary5)
    print(f"结果: {level5}")
    print(f"原因: {reason5}")
    assert level5 == "medium", f"预期 'medium'，实际 '{level5}'"
    print("  ✓ 测试通过")
    
    # 测试用例 6: LOW INTENT - 单次访问<6秒
    print("\n【测试用例 6】低意图 - 单次访问<6秒")
    print("-" * 80)
    summary6 = {
        "visit_count": 1,
        "max_stay_seconds": 4,
        "avg_stay_seconds": 4.0,
        "total_stay_seconds": 4,
        "has_enter_buy_page": False,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse"],
    }
    level6, reason6 = classify_intent(summary6)
    print(f"结果: {level6}")
    print(f"原因: {reason6}")
    assert level6 == "low", f"预期 'low'，实际 '{level6}'"
    print("  ✓ 测试通过")
    
    # 测试用例 7: MEDIUM INTENT - 单次访问但查看尺码表
    print("\n【测试用例 7】中等意图 - 单次访问但查看尺码表")
    print("-" * 80)
    summary7 = {
        "visit_count": 1,
        "max_stay_seconds": 20,
        "avg_stay_seconds": 20.0,
        "total_stay_seconds": 20,
        "has_enter_buy_page": False,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": True,
        "event_types": ["browse", "click_size_chart"],
    }
    level7, reason7 = classify_intent(summary7)
    print(f"结果: {level7}")
    print(f"原因: {reason7}")
    assert level7 == "medium", f"预期 'medium'，实际 '{level7}'"
    print("  ✓ 测试通过")
    
    # 测试用例 8: HESITATING - 多次快速访问无行动
    print("\n【测试用例 8】犹豫 - 多次快速访问无行动")
    print("-" * 80)
    summary8 = {
        "visit_count": 3,
        "max_stay_seconds": 8,
        "avg_stay_seconds": 6.0,
        "total_stay_seconds": 18,
        "has_enter_buy_page": False,
        "has_favorite": False,
        "has_share": False,
        "has_click_size_chart": False,
        "event_types": ["browse"],
    }
    level8, reason8 = classify_intent(summary8)
    print(f"结果: {level8}")
    print(f"原因: {reason8}")
    assert level8 == "hesitating", f"预期 'hesitating'，实际 '{level8}'"
    print("  ✓ 测试通过")
    
    print("\n" + "=" * 80)
    print("所有测试用例通过！")
    print("=" * 80)


if __name__ == "__main__":
    test_intent_classification()


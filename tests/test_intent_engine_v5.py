"""Tests for V5 intent engine (conservative, explainable, retail-aligned)."""
from __future__ import annotations

import pytest

from app.services.intent_engine import (
    INTENT_HESITATING,
    INTENT_HIGH,
    INTENT_LOW,
    INTENT_MEDIUM,
    IntentResult,
    classify_intent,
)


class TestIntentLevels:
    """测试所有 4 个意图级别。"""
    
    def test_high_intent_enter_buy_page(self):
        """测试：HIGH - 进入购买页（最强信号）。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 20,
            "avg_stay_seconds": 20.0,
            "has_enter_buy_page": True,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_HIGH
        assert "进入购买页面" in result.reason
        assert result.reason  # 非空
    
    def test_high_intent_add_to_cart(self):
        """测试：HIGH - 加购物车（强信号）。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 15,
            "avg_stay_seconds": 15.0,
            "has_add_to_cart": True,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_HIGH
        assert "加入购物车" in result.reason
        assert result.reason
    
    def test_high_intent_favorite_multiple_visits(self):
        """测试：HIGH - 收藏 + 多次访问（需要 2 次以上）。"""
        summary = {
            "visit_count": 2,
            "max_stay_seconds": 25,
            "avg_stay_seconds": 20.0,
            "has_favorite": True,
            "has_enter_buy_page": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_HIGH
        assert "收藏" in result.reason
        assert result.reason
    
    def test_hesitating_multiple_visits_no_action(self):
        """测试：HESITATING - 多次访问但无强信号。"""
        summary = {
            "visit_count": 3,
            "max_stay_seconds": 25,
            "avg_stay_seconds": 20.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "has_add_to_cart": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_HESITATING
        assert "访问" in result.reason
        assert "未采取购买相关行动" in result.reason or "犹豫" in result.reason
        assert result.reason
    
    def test_hesitating_long_stay_multiple_visits(self):
        """测试：HESITATING - 长停留 + 多次访问但无强信号。"""
        summary = {
            "visit_count": 2,
            "max_stay_seconds": 30,
            "avg_stay_seconds": 25.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_HESITATING
        assert result.reason
    
    def test_medium_intent_multiple_visits(self):
        """测试：MEDIUM - 2次以上访问 + 一定停留时间。"""
        summary = {
            "visit_count": 2,
            "max_stay_seconds": 20,
            "avg_stay_seconds": 18.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_MEDIUM
        assert result.reason
    
    def test_medium_intent_single_visit_long_stay(self):
        """测试：MEDIUM - 单次访问但停留时间较长。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 20,
            "avg_stay_seconds": 20.0,
            "has_click_size_chart": True,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_MEDIUM
        assert result.reason
    
    def test_low_intent_single_short_visit(self):
        """测试：LOW - 单次短暂访问。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 5,
            "avg_stay_seconds": 5.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_LOW
        assert result.reason


class TestEdgeCases:
    """测试边界情况。"""
    
    def test_empty_logs(self):
        """测试：空日志（visit_count = 0）。"""
        summary = {
            "visit_count": 0,
            "max_stay_seconds": 0,
            "avg_stay_seconds": 0.0,
        }
        result = classify_intent(summary)
        
        assert result.level == INTENT_LOW
        assert "未检测到访问记录" in result.reason or "访问记录" in result.reason
        assert result.reason
    
    def test_short_visits(self):
        """测试：多次短暂访问。"""
        summary = {
            "visit_count": 3,
            "max_stay_seconds": 8,
            "avg_stay_seconds": 6.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        # 应该是 hesitating 或 low
        assert result.level in (INTENT_HESITATING, INTENT_LOW)
        assert result.reason
    
    def test_repeat_visits_no_action(self):
        """测试：重复访问但无任何行动。"""
        summary = {
            "visit_count": 5,
            "max_stay_seconds": 15,
            "avg_stay_seconds": 12.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "has_add_to_cart": False,
        }
        result = classify_intent(summary)
        
        # 应该是 hesitating（多次访问但无强信号）
        assert result.level == INTENT_HESITATING
        assert result.reason
    
    def test_single_visit_favorite_not_high(self):
        """测试：单次访问 + 收藏（不应判定为 high，需要多次访问）。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 30,
            "avg_stay_seconds": 30.0,
            "has_favorite": True,
            "has_enter_buy_page": False,
        }
        result = classify_intent(summary)
        
        # 单次访问 + 收藏不应判定为 high（需要 2 次以上）
        assert result.level != INTENT_HIGH
        assert result.reason


class TestConservativeRules:
    """测试保守规则（宁可保守，不可激进）。"""
    
    def test_long_stay_without_strong_signal_not_high(self):
        """测试：长停留但无强信号不应判定为 high。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 60,
            "avg_stay_seconds": 60.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "has_add_to_cart": False,
        }
        result = classify_intent(summary)
        
        # 仅停留时间长不足以判定为 high（需要强信号）
        assert result.level != INTENT_HIGH
        assert result.reason
    
    def test_multiple_visits_long_stay_hesitating_not_high(self):
        """测试：多次访问 + 长停留但无强信号 = hesitating（不是 high）。"""
        summary = {
            "visit_count": 4,
            "max_stay_seconds": 45,
            "avg_stay_seconds": 35.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
            "has_add_to_cart": False,
        }
        result = classify_intent(summary)
        
        # 多次访问 + 长停留但无强信号 = hesitating（不是 high）
        assert result.level == INTENT_HESITATING
        assert result.reason


class TestIntentResultStructure:
    """测试 IntentResult 结构。"""
    
    def test_intent_result_never_none(self):
        """测试：intent_level 永远不为 None。"""
        summary = {
            "visit_count": 1,
            "max_stay_seconds": 10,
        }
        result = classify_intent(summary)
        
        assert result.level is not None
        assert result.level in (INTENT_HIGH, INTENT_MEDIUM, INTENT_LOW, INTENT_HESITATING)
        assert result.reason is not None
        assert result.reason.strip()  # 非空字符串
    
    def test_intent_result_always_has_reason(self):
        """测试：所有结果都有可读的原因。"""
        test_cases = [
            {"visit_count": 1, "max_stay_seconds": 5},
            {"visit_count": 2, "max_stay_seconds": 20, "has_favorite": True},
            {"visit_count": 3, "max_stay_seconds": 15},
            {"visit_count": 1, "max_stay_seconds": 30, "has_enter_buy_page": True},
        ]
        
        for summary in test_cases:
            result = classify_intent(summary)
            assert result.reason
            assert len(result.reason.strip()) > 0
            assert result.level is not None


class TestBusinessLogicAlignment:
    """测试业务逻辑对齐（真实零售导购判断）。"""
    
    def test_high_requires_strong_signal(self):
        """测试：high 需要强信号（进入购买页、加购物车、收藏+多次访问）。"""
        # 仅停留时间长不应判定为 high
        summary1 = {
            "visit_count": 1,
            "max_stay_seconds": 120,
            "avg_stay_seconds": 120.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
        }
        result1 = classify_intent(summary1)
        assert result1.level != INTENT_HIGH
        
        # 进入购买页应判定为 high
        summary2 = {
            "visit_count": 1,
            "max_stay_seconds": 10,
            "has_enter_buy_page": True,
        }
        result2 = classify_intent(summary2)
        assert result2.level == INTENT_HIGH
    
    def test_hesitating_vs_high(self):
        """测试：多次访问 + 长停留 = hesitating（不是 high）。"""
        summary = {
            "visit_count": 5,
            "max_stay_seconds": 50,
            "avg_stay_seconds": 40.0,
            "has_enter_buy_page": False,
            "has_favorite": False,
        }
        result = classify_intent(summary)
        
        # 应该是 hesitating，不是 high（因为没有强信号）
        assert result.level == INTENT_HESITATING
        assert result.level != INTENT_HIGH


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


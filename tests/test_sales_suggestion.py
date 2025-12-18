"""Tests for sales suggestion pack generation (V5.4.0+).

测试覆盖：
1. 所有 intent_level 的建议包生成
2. recommended_action 在允许集合中
3. message_pack 长度 >= 2
4. 每条消息包含行动建议关键词
5. 禁止词汇检测
6. LLM 失败降级
7. 向后兼容（final_message 等于 primary message）
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.context import AgentContext
from app.models.product import Product
from app.services.sales_suggestion_service import (
    ALLOWED_ACTIONS,
    ACTION_ASK_SIZE,
    ACTION_REASSURE_COMFORT,
    ACTION_SCENE_RECOMMENDATION,
    ACTION_SOFT_CHECK_IN,
    FORBIDDEN_MARKETING_WORDS,
    build_suggestion_pack,
    calculate_confidence,
    choose_recommended_action,
)


@pytest.fixture
def sample_product():
    """Create a sample product for testing."""
    product = Product(
        id=1,
        sku="TEST001",
        name="舒适运动鞋",
        price=458.0,
        tags=["舒适", "百搭", "时尚"],
        attributes={"color": "黑色", "scene": "运动", "material": "真皮"},
    )
    return product


@pytest.fixture
def behavior_summary_high():
    """Create a high intent behavior summary."""
    return {
        "visit_count": 3,
        "avg_stay_seconds": 45.0,
        "has_favorite": True,
        "has_enter_buy_page": True,
        "has_click_size_chart": True,
    }


@pytest.fixture
def behavior_summary_hesitating():
    """Create a hesitating intent behavior summary."""
    return {
        "visit_count": 4,
        "avg_stay_seconds": 30.0,
        "has_favorite": False,
        "has_enter_buy_page": False,
        "has_click_size_chart": False,
    }


@pytest.fixture
def behavior_summary_low():
    """Create a low intent behavior summary."""
    return {
        "visit_count": 1,
        "avg_stay_seconds": 5.0,
        "has_favorite": False,
        "has_enter_buy_page": False,
        "has_click_size_chart": False,
    }


class TestChooseRecommendedAction:
    """Test recommended action selection."""
    
    def test_high_intent_with_size_chart(self, sample_product, behavior_summary_high):
        """Test high intent with size chart click."""
        action, explanation = choose_recommended_action(
            intent_level="high",
            behavior_summary=behavior_summary_high,
            product=sample_product,
        )
        
        assert action == ACTION_ASK_SIZE
        assert "尺码" in explanation
    
    def test_high_intent_with_favorite(self, sample_product):
        """Test high intent with favorite."""
        behavior = {"has_favorite": True, "has_click_size_chart": False}
        action, explanation = choose_recommended_action(
            intent_level="high",
            behavior_summary=behavior,
            product=sample_product,
        )
        
        assert action == ACTION_MENTION_STOCK
        assert "库存" in explanation
    
    def test_hesitating_intent_multiple_visits(self, sample_product, behavior_summary_hesitating):
        """Test hesitating intent with multiple visits."""
        action, explanation = choose_recommended_action(
            intent_level="hesitating",
            behavior_summary=behavior_summary_hesitating,
            product=sample_product,
        )
        
        assert action == ACTION_REASSURE_COMFORT
        assert "舒适度" in explanation or "顾虑" in explanation
    
    def test_medium_intent_with_scene(self, sample_product):
        """Test medium intent with scene attribute."""
        action, explanation = choose_recommended_action(
            intent_level="medium",
            behavior_summary={},
            product=sample_product,
        )
        
        assert action == ACTION_SCENE_RECOMMENDATION
        assert "场景" in explanation
    
    def test_low_intent(self, sample_product, behavior_summary_low):
        """Test low intent."""
        action, explanation = choose_recommended_action(
            intent_level="low",
            behavior_summary=behavior_summary_low,
            product=sample_product,
        )
        
        assert action == ACTION_SOFT_CHECK_IN
        assert "轻量" in explanation or "不施压" in explanation
    
    def test_action_in_allowed_set(self, sample_product):
        """Test that all actions are in allowed set."""
        for intent_level in ["high", "hesitating", "medium", "low"]:
            action, _ = choose_recommended_action(
                intent_level=intent_level,
                behavior_summary={},
                product=sample_product,
            )
            assert action in ALLOWED_ACTIONS


class TestCalculateConfidence:
    """Test confidence calculation."""
    
    def test_high_intent_confidence(self, behavior_summary_high):
        """Test high intent confidence."""
        confidence = calculate_confidence("high", behavior_summary_high)
        assert confidence == "high"
    
    def test_hesitating_intent_confidence(self, behavior_summary_hesitating):
        """Test hesitating intent confidence."""
        confidence = calculate_confidence("hesitating", behavior_summary_hesitating)
        assert confidence in ["medium", "high"]
    
    def test_medium_intent_confidence(self):
        """Test medium intent confidence."""
        confidence = calculate_confidence("medium", {})
        assert confidence == "medium"
    
    def test_low_intent_confidence(self, behavior_summary_low):
        """Test low intent confidence."""
        confidence = calculate_confidence("low", behavior_summary_low)
        assert confidence == "low"
    
    def test_confidence_boosted_by_favorite(self):
        """Test confidence boosted by favorite."""
        behavior = {"has_favorite": True, "visit_count": 1}
        confidence = calculate_confidence("medium", behavior)
        assert confidence == "high"
    
    def test_confidence_boosted_by_multiple_visits(self):
        """Test confidence boosted by multiple visits."""
        behavior = {"visit_count": 3, "has_favorite": False}
        confidence = calculate_confidence("low", behavior)
        assert confidence == "medium"


class TestSalesSuggestionPack:
    """Test sales suggestion pack generation."""
    
    @pytest.mark.asyncio
    async def test_hesitating_intent_suggestion_pack(
        self, sample_product, behavior_summary_hesitating
    ):
        """Test hesitating intent suggestion pack."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="hesitating",
            behavior_summary=behavior_summary_hesitating,
            extra={"intent_reason": "用户多次访问但未下单", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        # 验证基本字段
        assert suggestion.intent_level == "hesitating"
        assert suggestion.confidence in ["medium", "high"]
        assert suggestion.why_now is not None
        assert len(suggestion.why_now) > 0
        
        # 验证 recommended_action
        assert suggestion.recommended_action in ALLOWED_ACTIONS
        assert suggestion.action_explanation is not None
        
        # 验证 message_pack
        assert len(suggestion.message_pack) >= 2
        assert any(msg.type == "primary" for msg in suggestion.message_pack)
        assert any(msg.type == "alternative" for msg in suggestion.message_pack)
        
        # 验证每条消息包含行动建议关键词
        action_keywords = {
            ACTION_ASK_SIZE: ["码", "尺码", "号"],
            ACTION_REASSURE_COMFORT: ["舒适", "舒服", "脚感"],
            ACTION_MENTION_STOCK: ["库存", "现货"],
            ACTION_SCENE_RECOMMENDATION: ["适合", "场景", "可以"],
            ACTION_SOFT_CHECK_IN: ["不错", "可以", "看看"],
        }
        
        keywords = action_keywords.get(suggestion.recommended_action, [])
        if keywords:
            for msg in suggestion.message_pack:
                assert any(kw in msg.message for kw in keywords), (
                    f"Message '{msg.message}' does not contain action keywords {keywords}"
                )
        
        # 验证禁止词汇
        for msg in suggestion.message_pack:
            for word in FORBIDDEN_MARKETING_WORDS:
                assert word not in msg.message, (
                    f"Message '{msg.message}' contains forbidden word: {word}"
                )
        
        # 验证 send_recommendation
        assert suggestion.send_recommendation.suggested is not None
        assert suggestion.send_recommendation.risk_level in ["low", "medium", "high"]
    
    @pytest.mark.asyncio
    async def test_high_intent_suggestion_pack(
        self, sample_product, behavior_summary_high
    ):
        """Test high intent suggestion pack."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="high",
            behavior_summary=behavior_summary_high,
            extra={"intent_reason": "用户已收藏商品", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        assert suggestion.intent_level == "high"
        assert suggestion.confidence == "high"
        assert suggestion.send_recommendation.suggested is True
        assert suggestion.send_recommendation.risk_level == "low"
        assert len(suggestion.message_pack) >= 2
    
    @pytest.mark.asyncio
    async def test_low_intent_suggestion_pack(
        self, sample_product, behavior_summary_low
    ):
        """Test low intent suggestion pack."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="low",
            behavior_summary=behavior_summary_low,
            extra={"intent_reason": "用户单次短暂访问", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        assert suggestion.intent_level == "low"
        assert suggestion.confidence == "low"
        assert suggestion.send_recommendation.suggested is False
        assert len(suggestion.message_pack) >= 2
        
        # 低意图不应该包含强烈的行动号召
        for msg in suggestion.message_pack:
            assert "必须" not in msg.message
            assert "一定要" not in msg.message
    
    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, sample_product, behavior_summary_hesitating):
        """Test fallback when LLM fails."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="hesitating",
            behavior_summary=behavior_summary_hesitating,
            extra={"intent_reason": "用户多次访问", "allowed": True},
        )
        
        # Mock LLM to raise error
        mock_llm = MagicMock()
        mock_llm.settings.llm_api_key = "test_key"
        mock_llm.settings.llm_base_url = "http://test.com"
        mock_llm.stream_chat = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch("app.services.sales_suggestion_service.get_llm_client", return_value=mock_llm):
            suggestion = await build_suggestion_pack(context)
            
            # Should still return 2 messages (fallback)
            assert len(suggestion.message_pack) >= 2
            assert suggestion.recommended_action in ALLOWED_ACTIONS
    
    @pytest.mark.asyncio
    async def test_message_pack_length_constraint(self, sample_product):
        """Test message pack respects length constraint."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="high",
            behavior_summary={"visit_count": 2, "has_favorite": True},
            extra={"intent_reason": "用户已收藏", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        # All messages should respect max_length (default 45)
        for msg in suggestion.message_pack:
            assert len(msg.message) <= 45, (
                f"Message '{msg.message}' exceeds max length: {len(msg.message)}"
            )
    
    @pytest.mark.asyncio
    async def test_backward_compatibility_primary_message(self, sample_product):
        """Test that primary message can be used as final_message."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="high",
            behavior_summary={"visit_count": 2},
            extra={"intent_reason": "用户多次访问", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        # Find primary message
        primary_msg = next(
            (msg for msg in suggestion.message_pack if msg.type == "primary"),
            suggestion.message_pack[0],
        )
        
        # Primary message should be valid and usable as final_message
        assert primary_msg.message is not None
        assert len(primary_msg.message) > 0
        assert len(primary_msg.message) <= 45


class TestActionKeywords:
    """Test that messages contain action keywords."""
    
    @pytest.mark.asyncio
    async def test_ask_size_contains_keywords(self, sample_product):
        """Test ask_size action contains size keywords."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="high",
            behavior_summary={"has_click_size_chart": True},
            extra={"intent_reason": "用户查看尺码表", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        assert suggestion.recommended_action == ACTION_ASK_SIZE
        
        # At least one message should contain size keywords
        size_keywords = ["码", "尺码", "号"]
        found = False
        for msg in suggestion.message_pack:
            if any(kw in msg.message for kw in size_keywords):
                found = True
                break
        assert found, "No message contains size keywords"
    
    @pytest.mark.asyncio
    async def test_scene_recommendation_contains_keywords(self, sample_product):
        """Test scene_recommendation action contains scene keywords."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="medium",
            behavior_summary={},
            extra={"intent_reason": "用户有一定兴趣", "allowed": True},
        )
        
        suggestion = await build_suggestion_pack(context)
        
        # At least one message should contain scene keywords
        scene_keywords = ["适合", "场景", "可以"]
        found = False
        for msg in suggestion.message_pack:
            if any(kw in msg.message for kw in scene_keywords):
                found = True
                break
        assert found, "No message contains scene keywords"


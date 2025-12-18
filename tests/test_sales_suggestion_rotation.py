"""Tests for sales suggestion pack with deterministic rotation (V5.6.0+).

测试覆盖：
1. 同一 (user_id, sku) 在同一窗口内 -> 相同的 message_pack
2. 不同窗口 -> message_pack 至少有一条消息或策略顺序不同
3. message_pack 有 >= 3 条消息且 >= 3 个不同策略
4. hesitating 主消息引用行为上下文
5. 禁止词汇不存在
6. 降级触发时仍返回有效包
7. 备选消息不是主消息的子串截断
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.context import AgentContext
from app.models.product import Product
from app.services.fallback_message_pack import generate_fallback_message_pack
from app.services.message_validators import validate_message_pack
from app.services.sales_suggestion_service import build_suggestion_pack
from app.services.strategy_rotation import (
    compute_rotation_key,
    get_rotation_window,
    select_strategies_for_pack,
)
from app.services.prompt_templates import FORBIDDEN_MARKETING_WORDS


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
def behavior_summary_hesitating():
    """Create a hesitating intent behavior summary."""
    return {
        "visit_count": 4,
        "avg_stay_seconds": 30.0,
        "has_favorite": False,
        "has_enter_buy_page": False,
        "has_click_size_chart": False,
    }


class TestDeterministicRotation:
    """Test deterministic rotation within same window."""
    
    def test_same_user_sku_same_window_identical_pack(self, sample_product, behavior_summary_hesitating):
        """Test same (user_id, sku) in same window produces identical message pack."""
        user_id = "user_001"
        sku = sample_product.sku
        window = get_rotation_window()
        
        # Compute rotation key
        rotation_key_1 = compute_rotation_key(user_id, sku, window)
        rotation_key_2 = compute_rotation_key(user_id, sku, window)
        
        assert rotation_key_1 == rotation_key_2, "Rotation keys should be identical in same window"
        
        # Generate message packs
        pack_1 = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=rotation_key_1,
            max_length=45,
            min_count=3,
        )
        
        pack_2 = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=rotation_key_2,
            max_length=45,
            min_count=3,
        )
        
        # Should be identical
        assert len(pack_1) == len(pack_2)
        assert [msg["message"] for msg in pack_1] == [msg["message"] for msg in pack_2]
        assert [msg["strategy"] for msg in pack_1] == [msg["strategy"] for msg in pack_2]
    
    def test_different_windows_different_pack(self, sample_product, behavior_summary_hesitating):
        """Test different windows produce different message packs."""
        user_id = "user_001"
        sku = sample_product.sku
        
        # Different windows
        window_1 = "2024-01-01-00"
        window_2 = "2024-01-01-06"
        
        rotation_key_1 = compute_rotation_key(user_id, sku, window_1)
        rotation_key_2 = compute_rotation_key(user_id, sku, window_2)
        
        # Generate message packs
        pack_1 = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=rotation_key_1,
            max_length=45,
            min_count=3,
        )
        
        pack_2 = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=rotation_key_2,
            max_length=45,
            min_count=3,
        )
        
        # Should differ in at least one message or strategy order
        messages_1 = [msg["message"] for msg in pack_1]
        messages_2 = [msg["message"] for msg in pack_2]
        strategies_1 = [msg["strategy"] for msg in pack_1]
        strategies_2 = [msg["strategy"] for msg in pack_2]
        
        assert messages_1 != messages_2 or strategies_1 != strategies_2, (
            "Message packs should differ across windows"
        )


class TestMessagePackQuality:
    """Test message pack quality requirements."""
    
    def test_message_pack_has_at_least_3_items_and_3_strategies(self, sample_product, behavior_summary_hesitating):
        """Test message pack has >= 3 items and >= 3 distinct strategies."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        assert len(pack) >= 3, f"Message pack should have >= 3 items, got {len(pack)}"
        
        strategies = [msg["strategy"] for msg in pack]
        unique_strategies = set(strategies)
        assert len(unique_strategies) >= 3, (
            f"Message pack should have >= 3 distinct strategies, got {len(unique_strategies)}: {strategies}"
        )
    
    def test_hesitating_primary_message_references_behavior(self, sample_product, behavior_summary_hesitating):
        """Test hesitating primary message references behavior context."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        
        # Should reference behavior (multiple visits or long stay)
        behavior_keywords = ["看了几次", "浏览", "访问", "停留"]
        assert any(kw in primary_message for kw in behavior_keywords), (
            f"Primary message should reference behavior context: {primary_message}"
        )
    
    def test_no_forbidden_words(self, sample_product, behavior_summary_hesitating):
        """Test no forbidden words in message pack."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        for msg in pack:
            message = msg["message"]
            for word in FORBIDDEN_MARKETING_WORDS:
                assert word not in message, (
                    f"Message '{message}' contains forbidden word: {word}"
                )
    
    def test_no_alternative_is_substring_truncation(self, sample_product, behavior_summary_hesitating):
        """Test no alternative is a substring truncation of primary."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        if len(pack) > 1:
            primary_message = pack[0]["message"]
            for i, msg in enumerate(pack[1:], 1):
                alt_message = msg["message"]
                # Check if alt is a substring truncation (simple heuristic)
                if alt_message in primary_message and len(alt_message) < len(primary_message) * 0.8:
                    pytest.fail(
                        f"Alternative message {i} is a substring truncation of primary: "
                        f"primary='{primary_message}', alt='{alt_message}'"
                    )


class TestFallbackBehavior:
    """Test fallback behavior when LLM fails."""
    
    @pytest.mark.asyncio
    async def test_fallback_still_returns_valid_pack(self, sample_product, behavior_summary_hesitating):
        """Test fallback triggers when LLM fails and still returns valid pack."""
        context = AgentContext(
            user_id="user_001",
            sku="TEST001",
            product=sample_product,
            intent_level="hesitating",
            behavior_summary=behavior_summary_hesitating,
            extra={"intent_reason": "用户多次访问但未下单", "allowed": True},
        )
        
        # Mock LLM to raise error
        mock_llm = MagicMock()
        mock_llm.settings.llm_api_key = "test_key"
        mock_llm.settings.llm_base_url = "http://test.com"
        mock_llm.stream_chat = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch("app.services.sales_suggestion_service.get_llm_client", return_value=mock_llm):
            suggestion = await build_suggestion_pack(context)
            
            # Should still return valid pack
            assert len(suggestion.message_pack) >= 3
            assert len(set(msg.strategy for msg in suggestion.message_pack)) >= 3
            
            # Validate message pack
            message_pack_dict = [
                {"strategy": msg.strategy, "message": msg.message} for msg in suggestion.message_pack
            ]
            is_valid, error = validate_message_pack(
                message_pack=message_pack_dict,
                current_sku=sample_product.sku,
                max_length=45,
                min_count=3,
            )
            assert is_valid, f"Fallback message pack validation failed: {error}"


class TestStrategySelection:
    """Test strategy selection logic."""
    
    def test_strategy_selection_for_hesitating(self, sample_product):
        """Test strategy selection for hesitating intent."""
        strategies = select_strategies_for_pack(
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            rotation_key=0,
            min_count=3,
        )
        
        assert len(strategies) >= 3
        strategy_names = [s[0] for s in strategies]
        unique_strategies = set(strategy_names)
        assert len(unique_strategies) >= 3, f"Should have >= 3 distinct strategies, got: {strategy_names}"
    
    def test_strategy_selection_for_high(self, sample_product):
        """Test strategy selection for high intent."""
        strategies = select_strategies_for_pack(
            intent_level="high",
            recommended_action="ask_size",
            rotation_key=0,
            min_count=3,
        )
        
        assert len(strategies) >= 3
        strategy_names = [s[0] for s in strategies]
        # Should include ask_size strategy
        assert "ask_size" in strategy_names or any("尺码" in s[1] for s in strategies)


class TestMessageValidation:
    """Test message validation."""
    
    def test_validate_message_pack_strategy_diversity(self, sample_product):
        """Test message pack validation requires strategy diversity."""
        # Valid pack (different strategies)
        valid_pack = [
            {"strategy": "询问顾虑", "message": "我看你最近看了几次，有什么顾虑吗？"},
            {"strategy": "询问尺码", "message": "您平时穿什么码？"},
            {"strategy": "场景推荐", "message": "适合日常运动，您觉得呢？"},
        ]
        
        is_valid, error = validate_message_pack(
            message_pack=valid_pack,
            current_sku=sample_product.sku,
            max_length=45,
            min_count=3,
        )
        assert is_valid, f"Valid pack should pass validation: {error}"
        
        # Invalid pack (duplicate strategies)
        invalid_pack = [
            {"strategy": "询问顾虑", "message": "有什么顾虑吗？"},
            {"strategy": "询问顾虑", "message": "您有什么顾虑吗？"},
            {"strategy": "询问顾虑", "message": "顾虑是什么呢？"},
        ]
        
        is_valid, error = validate_message_pack(
            message_pack=invalid_pack,
            current_sku=sample_product.sku,
            max_length=45,
            min_count=3,
        )
        assert not is_valid, "Invalid pack with duplicate strategies should fail validation"
        assert "策略重复" in error or "strategy" in error.lower()


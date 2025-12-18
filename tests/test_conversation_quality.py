"""Tests for conversation quality improvements (V5.8.0+).

测试覆盖：
1. guide_chat primary 包含"？"或疑问词
2. primary 不以完整商品名开头
3. primary 包含至少一个行动建议关键词
4. message_pack 有 >= 3 个不同策略
5. high intent primary 明确推进下一步
6. fallback 生成有效的对话式消息
7. followup_playbook 仅 high 和 hesitating 生成
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.context import AgentContext
from app.models.product import Product
from app.services.fallback_message_pack import generate_fallback_message_pack
from app.services.message_validators import (
    QUESTION_MARKERS,
    WEAK_PHRASES,
    validate_primary_message,
)
from app.services.sales_suggestion_service import (
    FollowupPlaybookItem,
    build_followup_playbook,
    build_suggestion_pack,
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


class TestPrimaryMessageQuality:
    """Test primary message quality requirements."""
    
    def test_primary_contains_question_marker(self, sample_product, behavior_summary_high):
        """Test primary message contains '？' or interrogative phrase."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="high",
            recommended_action="ask_size",
            behavior_summary=behavior_summary_high,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        
        # Should contain question marker
        has_question = any(marker in primary_message for marker in QUESTION_MARKERS)
        assert has_question, (
            f"Primary message should contain question marker, got: {primary_message}"
        )
    
    def test_primary_not_start_with_product_name(self, sample_product, behavior_summary_high):
        """Test primary message does not start with full product name."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="high",
            recommended_action="ask_size",
            behavior_summary=behavior_summary_high,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        product_name = sample_product.name
        
        # Should not start with product name
        assert not primary_message.strip().startswith(product_name), (
            f"Primary message should not start with product name '{product_name}', "
            f"got: {primary_message}"
        )
        
        # Should use "这款"/"这双" instead
        assert primary_message.startswith(("这款", "这双", "我看")) or "这款" in primary_message or "这双" in primary_message, (
            f"Primary message should use '这款'/'这双' instead of product name, "
            f"got: {primary_message}"
        )
    
    def test_primary_contains_action_hint(self, sample_product, behavior_summary_high):
        """Test primary message contains at least one action hint keyword."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="high",
            recommended_action="ask_size",
            behavior_summary=behavior_summary_high,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        
        # Should contain action hint keywords
        action_keywords = ["尺码", "码", "号", "脚感", "舒适", "场景", "适合", "库存", "优惠"]
        has_hint = any(keyword in primary_message for keyword in action_keywords)
        assert has_hint, (
            f"Primary message should contain action hint keyword, got: {primary_message}"
        )
    
    def test_primary_no_weak_phrases(self, sample_product, behavior_summary_high):
        """Test primary message does not contain weak phrases."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="high",
            recommended_action="ask_size",
            behavior_summary=behavior_summary_high,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        
        # Should not contain weak phrases
        for weak_phrase in WEAK_PHRASES:
            assert weak_phrase not in primary_message, (
                f"Primary message should not contain weak phrase '{weak_phrase}', "
                f"got: {primary_message}"
            )
    
    def test_primary_aligned_with_recommended_action(self, sample_product, behavior_summary_high):
        """Test primary message aligns with recommended_action."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="high",
            recommended_action="ask_size",
            behavior_summary=behavior_summary_high,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        
        # Should contain size-related keywords
        size_keywords = ["尺码", "码", "号", "穿多少码", "什么码"]
        has_size_hint = any(keyword in primary_message for keyword in size_keywords)
        assert has_size_hint, (
            f"Primary message should align with recommended_action=ask_size, "
            f"got: {primary_message}"
        )


class TestHighIntentPrimary:
    """Test high intent primary message pushes next step."""
    
    def test_high_intent_primary_pushes_next_step(self, sample_product, behavior_summary_high):
        """Test high intent primary clearly pushes next step."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="high",
            recommended_action="ask_size",
            behavior_summary=behavior_summary_high,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        primary_message = pack[0]["message"]
        
        # Should reference user action and ask concrete question
        has_reference = any(
            phrase in primary_message
            for phrase in ["刚进到购买页", "看得挺久", "看了几次", "进入购买页"]
        )
        has_concrete_question = any(
            phrase in primary_message
            for phrase in ["穿多少码", "什么码", "尺码", "码"]
        )
        
        assert has_reference or has_concrete_question, (
            f"High intent primary should reference user action and ask concrete question, "
            f"got: {primary_message}"
        )


class TestMessagePackStrategyDiversity:
    """Test message pack strategy diversity."""
    
    def test_message_pack_has_3_distinct_strategies(self, sample_product, behavior_summary_hesitating):
        """Test message pack has >= 3 distinct strategies."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        strategies = [msg["strategy"] for msg in pack]
        unique_strategies = set(strategies)
        
        assert len(unique_strategies) >= 3, (
            f"Message pack should have >= 3 distinct strategies, "
            f"got: {strategies} (unique: {unique_strategies})"
        )


class TestFallbackConversationStyle:
    """Test fallback produces valid conversation-style messages."""
    
    def test_fallback_produces_conversation_style(self, sample_product, behavior_summary_hesitating):
        """Test fallback produces valid conversation-style messages."""
        pack = generate_fallback_message_pack(
            product=sample_product,
            intent_level="hesitating",
            recommended_action="ask_concern_type",
            behavior_summary=behavior_summary_hesitating,
            rotation_key=0,
            max_length=45,
            min_count=3,
        )
        
        # All messages should be conversation-style (questions, not statements)
        for msg in pack:
            message = msg["message"]
            # Should contain question marker or be conversational
            has_question = any(marker in message for marker in QUESTION_MARKERS)
            is_conversational = any(
                phrase in message
                for phrase in ["～", "我帮你", "我可以", "你觉得", "你觉得呢"]
            )
            
            assert has_question or is_conversational, (
                f"Message should be conversation-style, got: {message}"
            )


class TestFollowupPlaybook:
    """Test follow-up playbook generation."""
    
    def test_playbook_only_for_high_and_hesitating(self):
        """Test playbook only generated for high and hesitating intent."""
        # High intent
        playbook_high = build_followup_playbook(
            intent_level="high",
            recommended_action="ask_size",
        )
        assert len(playbook_high) > 0, "High intent should generate playbook"
        
        # Hesitating intent
        playbook_hesitating = build_followup_playbook(
            intent_level="hesitating",
            recommended_action="ask_concern_type",
        )
        assert len(playbook_hesitating) > 0, "Hesitating intent should generate playbook"
        
        # Medium intent
        playbook_medium = build_followup_playbook(
            intent_level="medium",
            recommended_action="scene_relate",
        )
        assert len(playbook_medium) == 0, "Medium intent should not generate playbook"
        
        # Low intent
        playbook_low = build_followup_playbook(
            intent_level="low",
            recommended_action="soft_check_in",
        )
        assert len(playbook_low) == 0, "Low intent should not generate playbook"
    
    def test_playbook_items_are_short_and_copyable(self):
        """Test playbook items are short and directly copyable."""
        playbook = build_followup_playbook(
            intent_level="high",
            recommended_action="ask_size",
        )
        
        for item in playbook:
            assert len(item.reply) <= 50, (
                f"Playbook reply should be short (<= 50 chars), "
                f"got: {item.reply} ({len(item.reply)} chars)"
            )
            assert item.condition, "Playbook condition should not be empty"
            assert item.reply, "Playbook reply should not be empty"


class TestPrimaryMessageValidation:
    """Test primary message validation."""
    
    def test_validate_primary_message_rejects_no_question(self, sample_product):
        """Test validate_primary_message rejects message without question."""
        invalid_message = "这款舒适运动鞋很舒适，穿着很舒服"
        
        is_valid, error = validate_primary_message(
            message=invalid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            recommended_action="ask_size",
            max_length=45,
        )
        
        assert not is_valid, "Primary message without question should be rejected"
        assert "问句" in error or "question" in error.lower()
    
    def test_validate_primary_message_rejects_starts_with_product_name(self, sample_product):
        """Test validate_primary_message rejects message starting with product name."""
        invalid_message = f"{sample_product.name}，您平时穿什么码？"
        
        is_valid, error = validate_primary_message(
            message=invalid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            recommended_action="ask_size",
            max_length=45,
        )
        
        assert not is_valid, "Primary message starting with product name should be rejected"
        assert "商品名" in error or "product name" in error.lower()
    
    def test_validate_primary_message_rejects_weak_phrases(self, sample_product):
        """Test validate_primary_message rejects message with weak phrases."""
        invalid_message = "这款可以看看，您觉得呢？"
        
        is_valid, error = validate_primary_message(
            message=invalid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            recommended_action="ask_size",
            max_length=45,
        )
        
        assert not is_valid, "Primary message with weak phrases should be rejected"
        assert "弱化短语" in error or "weak" in error.lower()
    
    def test_validate_primary_message_accepts_valid_message(self, sample_product):
        """Test validate_primary_message accepts valid message."""
        valid_message = "我看你刚进到购买页了～你平时穿多少码？我帮你对一下更稳～"
        
        is_valid, error = validate_primary_message(
            message=valid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            recommended_action="ask_size",
            max_length=45,
        )
        
        assert is_valid, f"Valid primary message should be accepted, got error: {error}"


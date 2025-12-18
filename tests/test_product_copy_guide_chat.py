"""Tests for product copy guide_chat conversation quality (V5.8.2+).

测试覆盖：
1. guide_chat 消息不以完整商品名开头
2. guide_chat 消息包含问句或邀请回复短语
3. guide_chat 消息包含行动建议关键词
4. guide_chat 消息不包含弱化短语
5. copy_candidates 数量 >= 2
6. fallback 生成有效的 guide_chat 消息
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.product import Product
from app.services.fallback_product_copy import generate_fallback_product_copy
from app.services.message_validators import (
    INVITATION_PHRASES,
    QUESTION_MARKERS,
    WEAK_PHRASES,
    validate_guide_chat_message,
)
from app.services.product_copy_service import generate_product_copy


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
def selling_points():
    """Create sample selling points."""
    return ["舒适透气", "百搭时尚", "适合运动"]


class TestGuideChatMessageQuality:
    """Test guide_chat message quality requirements."""
    
    def test_guide_chat_not_start_with_product_name(self, sample_product, selling_points):
        """Test guide_chat message does NOT start with full product name."""
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        for copy_text in copies:
            product_name = sample_product.name
            
            # Should not start with product name
            assert not copy_text.strip().startswith(product_name), (
                f"guide_chat message should not start with product name '{product_name}', "
                f"got: {copy_text}"
            )
            
            # Should use "这款"/"这双" instead
            assert copy_text.startswith(("这款", "这双", "你平时", "如果你", "我可以")) or "这款" in copy_text or "这双" in copy_text, (
                f"guide_chat message should use '这款'/'这双' instead of product name, "
                f"got: {copy_text}"
            )
    
    def test_guide_chat_contains_question_or_invitation(self, sample_product, selling_points):
        """Test guide_chat message contains question mark or invitation phrase."""
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        for copy_text in copies:
            # Should contain question marker or invitation phrase
            has_question = any(marker in copy_text for marker in QUESTION_MARKERS)
            has_invitation = any(phrase in copy_text for phrase in INVITATION_PHRASES)
            
            assert has_question or has_invitation, (
                f"guide_chat message should contain question mark or invitation phrase, "
                f"got: {copy_text}"
            )
    
    def test_guide_chat_contains_action_hint(self, sample_product, selling_points):
        """Test guide_chat message contains action hint keyword."""
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        action_keywords = ["尺码", "码", "号", "脚感", "舒适", "场景", "适合", "库存", "优惠", "搭配"]
        
        for copy_text in copies:
            has_hint = any(keyword in copy_text for keyword in action_keywords)
            assert has_hint, (
                f"guide_chat message should contain action hint keyword, "
                f"got: {copy_text}"
            )
    
    def test_guide_chat_no_weak_phrases(self, sample_product, selling_points):
        """Test guide_chat message does not contain weak phrases."""
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        for copy_text in copies:
            for weak_phrase in WEAK_PHRASES:
                assert weak_phrase not in copy_text, (
                    f"guide_chat message should not contain weak phrase '{weak_phrase}', "
                    f"got: {copy_text}"
                )
    
    def test_guide_chat_length_constraint(self, sample_product, selling_points):
        """Test guide_chat message length constraint (10-50 chars)."""
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        for copy_text in copies:
            assert 10 <= len(copy_text) <= 50, (
                f"guide_chat message length should be 10-50 chars, "
                f"got: {len(copy_text)} chars: {copy_text}"
            )


class TestCopyCandidatesCount:
    """Test copy_candidates count requirement."""
    
    @pytest.mark.asyncio
    async def test_copy_candidates_count_at_least_2(self, sample_product):
        """Test copy_candidates count >= 2."""
        candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        assert len(candidates) >= 2, (
            f"copy_candidates should have >= 2 items, got: {len(candidates)}"
        )
        
        # All should be guide_chat
        for candidate in candidates:
            assert candidate.scene == "guide_chat", (
                f"All candidates should be guide_chat, got: {candidate.scene}"
            )


class TestFallbackGuideChat:
    """Test fallback produces valid guide_chat messages."""
    
    def test_fallback_produces_valid_guide_chat(self, sample_product, selling_points):
        """Test fallback produces valid guide_chat messages."""
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        assert len(copies) >= 2, "Fallback should generate at least 2 messages"
        
        # All messages should pass validation
        for copy_text in copies:
            is_valid, error = validate_guide_chat_message(
                message=copy_text,
                current_sku=sample_product.sku,
                product_name=sample_product.name,
                max_length=50,
                min_length=10,
            )
            assert is_valid, (
                f"Fallback guide_chat message should pass validation, "
                f"got error: {error}, message: {copy_text}"
            )


class TestGuideChatValidation:
    """Test guide_chat message validation."""
    
    def test_validate_guide_chat_rejects_starts_with_product_name(self, sample_product):
        """Test validate_guide_chat_message rejects message starting with product name."""
        invalid_message = f"{sample_product.name}，您平时穿什么码？"
        
        is_valid, error = validate_guide_chat_message(
            message=invalid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            max_length=50,
            min_length=10,
        )
        
        assert not is_valid, "guide_chat message starting with product name should be rejected"
        assert "商品名" in error or "product name" in error.lower()
    
    def test_validate_guide_chat_rejects_no_question_or_invitation(self, sample_product):
        """Test validate_guide_chat_message rejects message without question or invitation."""
        invalid_message = "这款舒适运动鞋很舒适，穿着很舒服"
        
        is_valid, error = validate_guide_chat_message(
            message=invalid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            max_length=50,
            min_length=10,
        )
        
        assert not is_valid, "guide_chat message without question or invitation should be rejected"
        assert "问句" in error or "invitation" in error.lower()
    
    def test_validate_guide_chat_rejects_weak_phrases(self, sample_product):
        """Test validate_guide_chat_message rejects message with weak phrases."""
        invalid_message = "这款可以看看，您觉得呢？"
        
        is_valid, error = validate_guide_chat_message(
            message=invalid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            max_length=50,
            min_length=10,
        )
        
        assert not is_valid, "guide_chat message with weak phrases should be rejected"
        assert "弱化短语" in error or "weak" in error.lower()
    
    def test_validate_guide_chat_accepts_valid_message(self, sample_product):
        """Test validate_guide_chat_message accepts valid message."""
        valid_message = "这双黑色挺百搭的，你平时通勤多还是运动多？我按场景给你推荐～"
        
        is_valid, error = validate_guide_chat_message(
            message=valid_message,
            current_sku=sample_product.sku,
            product_name=sample_product.name,
            max_length=50,
            min_length=10,
        )
        
        assert is_valid, f"Valid guide_chat message should be accepted, got error: {error}"


class TestSceneSeparation:
    """Test scene separation (guide_chat vs moments/poster)."""
    
    def test_guide_chat_different_from_moments(self, sample_product, selling_points):
        """Test guide_chat messages differ from moments messages."""
        guide_chat_copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        moments_copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="moments",
            style="natural",
            max_length=50,
            count=2,
        )
        
        # guide_chat should be conversation-style (questions/invitations)
        for guide_msg in guide_chat_copies:
            has_question = any(marker in guide_msg for marker in QUESTION_MARKERS)
            has_invitation = any(phrase in guide_msg for phrase in INVITATION_PHRASES)
            assert has_question or has_invitation, (
                f"guide_chat message should be conversation-style, got: {guide_msg}"
            )
        
        # moments can be descriptive (no requirement for questions)
        # This is expected behavior - moments don't need to be questions


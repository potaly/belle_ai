"""Tests for private-chat sales copy generation (V5.3.0+).

测试覆盖：
1. 所有 intent_level 的输出验证
2. 禁止词汇检测
3. 长度约束
4. LLM 失败降级
5. 输出必须包含行动建议关键词
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.product import Product
from app.services.fallback_copy import generate_fallback_copy
from app.services.prompt_templates import (
    FORBIDDEN_MARKETING_WORDS,
    build_system_prompt,
    build_user_prompt,
    validate_copy_output,
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
def behavior_summary():
    """Create a sample behavior summary."""
    return {
        "visit_count": 2,
        "avg_stay_seconds": 30.0,
        "has_favorite": False,
        "has_enter_buy_page": False,
    }


class TestPromptTemplates:
    """Test prompt template generation."""
    
    def test_build_system_prompt(self):
        """Test system prompt generation."""
        prompt = build_system_prompt()
        
        assert "导购" in prompt
        assert "1 对 1 私聊" in prompt
        assert "禁止" in prompt
        assert "营销词汇" in prompt
    
    def test_build_user_prompt_high_intent(self, sample_product):
        """Test user prompt for high intent."""
        prompt = build_user_prompt(
            product=sample_product,
            intent_level="high",
            intent_reason="用户多次访问并收藏",
            max_length=45,
        )
        
        assert "商品信息" in prompt
        assert "舒适运动鞋" in prompt
        assert "意图级别：high" in prompt
        assert "尺码" in prompt or "库存" in prompt
    
    def test_build_user_prompt_low_intent(self, sample_product):
        """Test user prompt for low intent."""
        prompt = build_user_prompt(
            product=sample_product,
            intent_level="low",
            intent_reason="用户单次短暂访问",
            max_length=45,
        )
        
        assert "意图级别：low" in prompt
        assert "克制" in prompt
        assert "不要强推" in prompt
    
    def test_validate_copy_output_valid(self):
        """Test validation of valid copy."""
        copy = "这款黑色运动鞋很舒适，您平时穿什么码？"
        is_valid, error = validate_copy_output(copy, max_length=45)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_copy_output_too_long(self):
        """Test validation of copy that exceeds length limit."""
        copy = "这是一款非常舒适的运动鞋，适合日常运动穿着，材质很好，价格也很实惠，您觉得怎么样？"  # > 45 chars
        is_valid, error = validate_copy_output(copy, max_length=45)
        
        assert is_valid is False
        assert "长度" in error
    
    def test_validate_copy_output_forbidden_words(self):
        """Test validation of copy with forbidden marketing words."""
        for word in FORBIDDEN_MARKETING_WORDS[:3]:  # Test first 3
            copy = f"这款鞋子{word}，建议购买"
            is_valid, error = validate_copy_output(copy, max_length=45)
            
            assert is_valid is False
            assert word in error
    
    def test_validate_copy_output_empty(self):
        """Test validation of empty copy."""
        is_valid, error = validate_copy_output("", max_length=45)
        
        assert is_valid is False
        assert "为空" in error


class TestFallbackCopy:
    """Test fallback copy generation."""
    
    def test_fallback_high_intent(self, sample_product):
        """Test fallback copy for high intent."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="high",
            max_length=45,
        )
        
        assert len(copy) <= 45
        assert "舒适运动鞋" in copy or "运动鞋" in copy
        # Should contain action suggestion
        assert any(keyword in copy for keyword in ["码", "库存", "尺码"])
    
    def test_fallback_hesitating_intent(self, sample_product):
        """Test fallback copy for hesitating intent."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="hesitating",
            max_length=45,
        )
        
        assert len(copy) <= 45
        assert "舒适" in copy or "运动鞋" in copy
        # Should contain light question
        assert any(keyword in copy for keyword in ["呢", "吗", "怎么样", "觉得"])
    
    def test_fallback_medium_intent(self, sample_product):
        """Test fallback copy for medium intent."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="medium",
            max_length=45,
        )
        
        assert len(copy) <= 45
        assert "运动鞋" in copy or "舒适" in copy
        # Should contain scene recommendation
        assert any(keyword in copy for keyword in ["适合", "场景", "运动", "可以"])
    
    def test_fallback_low_intent(self, sample_product):
        """Test fallback copy for low intent."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="low",
            max_length=45,
        )
        
        assert len(copy) <= 45
        assert "运动鞋" in copy or "舒适" in copy
        # Should NOT contain strong call-to-action
        assert "必须" not in copy
        assert "一定要" not in copy
    
    def test_fallback_respects_max_length(self, sample_product):
        """Test that fallback respects max_length constraint."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="high",
            max_length=20,  # Very short
        )
        
        assert len(copy) <= 20
    
    def test_fallback_no_forbidden_words(self, sample_product):
        """Test that fallback does not contain forbidden words."""
        for intent_level in ["high", "hesitating", "medium", "low"]:
            copy = generate_fallback_copy(
                product=sample_product,
                intent_level=intent_level,
                max_length=45,
            )
            
            for word in FORBIDDEN_MARKETING_WORDS:
                assert word not in copy, f"Fallback copy contains forbidden word: {word}"


class TestCopyServiceIntegration:
    """Test copy service integration with LLM and fallback."""
    
    @pytest.mark.asyncio
    async def test_copy_service_llm_success(self, sample_product, behavior_summary):
        """Test copy service with successful LLM generation."""
        from app.services.copy_service import generate_private_chat_copy
        from sqlalchemy.orm import Session
        
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock LLM client
        mock_llm = AsyncMock()
        mock_llm.stream_chat = AsyncMock(return_value=iter(["这款黑色运动鞋很舒适，您平时穿什么码？"]))
        
        with patch("app.services.copy_service.get_llm_client", return_value=mock_llm):
            with patch("app.services.copy_service.get_product_by_sku", return_value=sample_product):
                copy, llm_used, strategy = await generate_private_chat_copy(
                    db=db,
                    sku="TEST001",
                    intent_level="high",
                    intent_reason="用户多次访问并收藏",
                    behavior_summary=behavior_summary,
                )
                
                assert copy is not None
                assert len(copy) > 0
                assert llm_used is True
                assert "策略" in strategy or "推进" in strategy
    
    @pytest.mark.asyncio
    async def test_copy_service_llm_failure_fallback(self, sample_product):
        """Test copy service falls back when LLM fails."""
        from app.services.copy_service import generate_private_chat_copy
        from sqlalchemy.orm import Session
        
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock LLM client that raises error
        mock_llm = MagicMock()
        mock_llm.settings.llm_api_key = "test_key"
        mock_llm.settings.llm_base_url = "http://test.com"
        mock_llm.stream_chat = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch("app.services.copy_service.get_llm_client", return_value=mock_llm):
            with patch("app.services.copy_service.get_product_by_sku", return_value=sample_product):
                copy, llm_used, strategy = await generate_private_chat_copy(
                    db=db,
                    sku="TEST001",
                    intent_level="high",
                    intent_reason="用户多次访问",
                )
                
                assert copy is not None
                assert len(copy) > 0
                assert llm_used is False  # Should use fallback
    
    @pytest.mark.asyncio
    async def test_copy_service_validation_failure_fallback(self, sample_product):
        """Test copy service falls back when LLM output fails validation."""
        from app.services.copy_service import generate_private_chat_copy
        from sqlalchemy.orm import Session
        
        # Mock database session
        db = MagicMock(spec=Session)
        
        # Mock LLM that returns invalid output (contains forbidden word)
        mock_llm = MagicMock()
        mock_llm.settings.llm_api_key = "test_key"
        mock_llm.settings.llm_base_url = "http://test.com"
        mock_llm.stream_chat = AsyncMock(return_value=iter(["这款鞋子太香了，必入！"]))
        
        with patch("app.services.copy_service.get_llm_client", return_value=mock_llm):
            with patch("app.services.copy_service.get_product_by_sku", return_value=sample_product):
                copy, llm_used, strategy = await generate_private_chat_copy(
                    db=db,
                    sku="TEST001",
                    intent_level="high",
                    intent_reason="用户多次访问",
                )
                
                assert copy is not None
                assert len(copy) > 0
                assert llm_used is False  # Should use fallback due to validation failure
                # Fallback should not contain forbidden words
                assert "太香了" not in copy
                assert "必入" not in copy


class TestActionKeywords:
    """Test that copy contains action keywords."""
    
    def test_high_intent_contains_action_keyword(self, sample_product):
        """Test high intent copy contains action keyword."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="high",
            max_length=45,
        )
        
        # Should contain at least one action keyword
        action_keywords = ["码", "尺码", "库存", "促销", "舒适", "适合"]
        assert any(keyword in copy for keyword in action_keywords)
    
    def test_hesitating_intent_contains_question(self, sample_product):
        """Test hesitating intent copy contains question."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="hesitating",
            max_length=45,
        )
        
        # Should contain question marker
        question_markers = ["呢", "吗", "怎么样", "觉得", "？"]
        assert any(marker in copy for marker in question_markers)
    
    def test_medium_intent_contains_scene(self, sample_product):
        """Test medium intent copy contains scene recommendation."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="medium",
            max_length=45,
        )
        
        # Should contain scene-related keyword
        scene_keywords = ["适合", "场景", "运动", "可以", "搭配"]
        assert any(keyword in copy for keyword in scene_keywords)
    
    def test_low_intent_no_strong_cta(self, sample_product):
        """Test low intent copy does not contain strong CTA."""
        copy = generate_fallback_copy(
            product=sample_product,
            intent_level="low",
            max_length=45,
        )
        
        # Should NOT contain strong CTA
        strong_cta = ["必须", "一定要", "立即", "马上", "赶快"]
        assert not any(cta in copy for cta in strong_cta)


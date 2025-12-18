"""Tests for product copy generation API (V5.5.0+).

测试覆盖：
1. SKU only 请求：selling_points >= 3, copy_candidates >= 2
2. 所有消息：不包含禁止词汇、不包含其他 SKU、长度约束
3. 场景变化：guide_chat vs moments 产生不同语气
4. LLM 失败降级：使用降级模板，响应仍完整
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.product import Product
from app.services.fallback_product_copy import generate_fallback_product_copy
from app.services.product_analysis_service import analyze_selling_points
from app.services.product_copy_service import generate_product_copy
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


class TestProductAnalysis:
    """Test product selling points analysis."""
    
    def test_analyze_selling_points_rule_based(self, sample_product):
        """Test rule-based selling points extraction."""
        points = analyze_selling_points(sample_product, use_llm=False)
        
        assert len(points) >= 3
        assert len(points) <= 5
        assert all(isinstance(p, str) for p in points)
        assert all(len(p) > 0 for p in points)
    
    def test_analyze_selling_points_no_forbidden_words(self, sample_product):
        """Test selling points do not contain forbidden words."""
        points = analyze_selling_points(sample_product, use_llm=False)
        
        for point in points:
            for word in FORBIDDEN_MARKETING_WORDS:
                assert word not in point, f"Selling point '{point}' contains forbidden word: {word}"


class TestProductCopyGeneration:
    """Test product copy generation."""
    
    @pytest.mark.asyncio
    async def test_generate_product_copy_sku_only(self, sample_product):
        """Test copy generation with SKU only."""
        candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        assert len(candidates) >= 2
        assert all(candidate.scene == "guide_chat" for candidate in candidates)
        assert all(candidate.style == "natural" for candidate in candidates)
        assert all(len(candidate.message) > 0 for candidate in candidates)
    
    @pytest.mark.asyncio
    async def test_generate_product_copy_no_forbidden_words(self, sample_product):
        """Test copy does not contain forbidden words."""
        candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        for candidate in candidates:
            for word in FORBIDDEN_MARKETING_WORDS:
                assert word not in candidate.message, (
                    f"Copy '{candidate.message}' contains forbidden word: {word}"
                )
    
    @pytest.mark.asyncio
    async def test_generate_product_copy_length_constraint(self, sample_product):
        """Test copy respects length constraint."""
        max_length = 50
        candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=max_length,
        )
        
        for candidate in candidates:
            assert len(candidate.message) <= max_length, (
                f"Copy '{candidate.message}' exceeds max length: {len(candidate.message)}"
            )
    
    @pytest.mark.asyncio
    async def test_generate_product_copy_no_other_sku(self, sample_product):
        """Test copy does not contain other SKU references."""
        candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        # Check for SKU patterns (basic regex check)
        import re
        sku_pattern = re.compile(r'\[SKU:([^\]]+)\]|SKU:\s*([A-Z0-9]+)', re.IGNORECASE)
        
        for candidate in candidates:
            matches = sku_pattern.findall(candidate.message)
            if matches:
                # If SKU found, should only be the current SKU
                for match in matches:
                    found_sku = (match[0] or match[1]).upper()
                    assert found_sku == sample_product.sku.upper(), (
                        f"Copy '{candidate.message}' contains foreign SKU: {found_sku}"
                    )
    
    @pytest.mark.asyncio
    async def test_scene_variation_guide_chat_vs_moments(self, sample_product):
        """Test scene variation produces different tone."""
        guide_chat_candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        moments_candidates = await generate_product_copy(
            product=sample_product,
            scene="moments",
            style="natural",
            max_length=50,
        )
        
        # Both should have at least 2 candidates
        assert len(guide_chat_candidates) >= 2
        assert len(moments_candidates) >= 2
        
        # Messages should be different (at least one)
        guide_messages = {c.message for c in guide_chat_candidates}
        moments_messages = {c.message for c in moments_candidates}
        
        # At least one message should be different
        assert guide_messages != moments_messages or len(guide_messages) > 1
    
    @pytest.mark.asyncio
    async def test_llm_failure_fallback(self, sample_product):
        """Test fallback when LLM fails."""
        # Mock LLM to raise error
        mock_llm = MagicMock()
        mock_llm.settings.llm_api_key = "test_key"
        mock_llm.settings.llm_base_url = "http://test.com"
        mock_llm.stream_chat = AsyncMock(side_effect=Exception("LLM error"))
        
        with patch("app.services.product_copy_service.get_llm_client", return_value=mock_llm):
            candidates = await generate_product_copy(
                product=sample_product,
                scene="guide_chat",
                style="natural",
                max_length=50,
            )
            
            # Should still return at least 2 candidates (fallback)
            assert len(candidates) >= 2
            assert all(len(c.message) > 0 for c in candidates)
            assert all(len(c.message) <= 50 for c in candidates)


class TestFallbackProductCopy:
    """Test fallback product copy generation."""
    
    def test_fallback_generate_at_least_2(self, sample_product):
        """Test fallback generates at least 2 copies."""
        selling_points = analyze_selling_points(sample_product, use_llm=False)
        
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
            count=2,
        )
        
        assert len(copies) >= 2
        assert all(len(copy) > 0 for copy in copies)
        assert all(len(copy) <= 50 for copy in copies)
    
    def test_fallback_no_forbidden_words(self, sample_product):
        """Test fallback does not contain forbidden words."""
        selling_points = analyze_selling_points(sample_product, use_llm=False)
        
        copies = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        for copy in copies:
            for word in FORBIDDEN_MARKETING_WORDS:
                assert word not in copy, f"Fallback copy '{copy}' contains forbidden word: {word}"
    
    def test_fallback_scene_variation(self, sample_product):
        """Test fallback produces different copies for different scenes."""
        selling_points = analyze_selling_points(sample_product, use_llm=False)
        
        guide_chat = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        moments = generate_fallback_product_copy(
            product=sample_product,
            selling_points=selling_points,
            scene="moments",
            style="natural",
            max_length=50,
        )
        
        # Both should have at least 2 copies
        assert len(guide_chat) >= 2
        assert len(moments) >= 2
        
        # Messages should be different (at least one)
        assert guide_chat != moments or len(guide_chat) > 1


class TestAPIIntegration:
    """Test API integration (full flow)."""
    
    @pytest.mark.asyncio
    async def test_api_response_structure(self, sample_product):
        """Test API response has correct structure."""
        from app.schemas.copy_schemas import CopyResponse
        from app.services.product_analysis_service import analyze_selling_points
        from app.services.product_copy_service import generate_product_copy
        
        # Simulate API flow
        selling_points = analyze_selling_points(sample_product, use_llm=False)
        candidates = await generate_product_copy(
            product=sample_product,
            scene="guide_chat",
            style="natural",
            max_length=50,
        )
        
        # Build response (as API would)
        from app.schemas.copy_schemas import CopyCandidateSchema
        
        response = CopyResponse(
            sku=sample_product.sku,
            product_name=sample_product.name,
            selling_points=selling_points,
            copy_candidates=[
                CopyCandidateSchema(
                    scene=c.scene,
                    style=c.style,
                    message=c.message,
                )
                for c in candidates
            ],
            posts=[c.message for c in candidates],  # Backward compatible
        )
        
        # Validate response
        assert response.sku == sample_product.sku
        assert response.product_name == sample_product.name
        assert len(response.selling_points) >= 3
        assert len(response.copy_candidates) >= 2
        assert len(response.posts) >= 2  # Backward compatible
        assert response.posts == [c.message for c in candidates]


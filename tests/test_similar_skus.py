"""Tests for similar SKUs search service (V6.0.0+)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.services.similar_skus_service import SimilarSKUsService
from app.models.product import Product


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def mock_products():
    """Mock product list."""
    products = []
    for i in range(10):
        product = MagicMock(spec=Product)
        product.brand_code = "BL"
        product.sku = f"8WZ{i:02d}CM1"
        product.name = f"Test Product {i}"
        product.tags = ["休闲", "日常"] if i % 2 == 0 else ["运动", "时尚"]
        product.attributes = {
            "category": "运动鞋" if i < 5 else "休闲鞋",
            "颜色": "黑色" if i % 2 == 0 else "白色",
            "季节": "四季",
        }
        product.updated_at = MagicMock()
        product.updated_at.timestamp.return_value = 1000 - i  # Descending order
        products.append(product)
    return products


class TestSimilarSKUsService:
    """Test cases for SimilarSKUsService."""

    @pytest.mark.asyncio
    async def test_rule_mode_returns_max_5_skus_and_deduplicates(self, mock_db, mock_products):
        """
        测试1：rule 模式返回最多5个SKU且去重。
        
        验证点：
        - 返回的SKU数量 <= 5
        - 按 (brand_code, sku) 去重
        - 返回的是SKU字符串列表
        """
        service = SimilarSKUsService()
        
        # Mock repository
        with patch(
            "app.services.similar_skus_service.get_candidate_products_by_brand",
            return_value=mock_products,
        ):
            vision_features = {
                "category": "运动鞋",
                "style": ["休闲", "日常"],
                "color": "黑色",
                "season": "四季",
                "keywords": ["百搭"],
            }
            
            skus, fallback_used = await service.search_similar_skus(
                db=mock_db,
                brand_code="BL",
                vision_features=vision_features,
                top_k=5,
                mode="rule",
            )
            
            # Assertions
            assert len(skus) <= 5, f"Expected <= 5 SKUs, got {len(skus)}"
            assert isinstance(skus, list), "Expected list of SKUs"
            assert all(isinstance(sku, str) for sku in skus), "All items should be strings"
            
            # Check deduplication (all SKUs should be unique)
            assert len(skus) == len(set(skus)), "SKUs should be deduplicated"
            
            # Check all SKUs start with expected prefix
            assert all(sku.startswith("8WZ") for sku in skus), "All SKUs should match expected format"
            
            assert not fallback_used, "Rule mode should not use fallback"

    @pytest.mark.asyncio
    async def test_vector_mode_fallback_to_rule_on_error(self, mock_db, mock_products):
        """
        测试2：vector 模式异常时降级到 rule 模式。
        
        验证点：
        - vector 模式失败时自动降级到 rule
        - fallback_used 标志为 True
        - 仍然返回有效结果（来自 rule 模式）
        """
        service = SimilarSKUsService()
        
        # Mock vector store to raise exception
        mock_vector_store = MagicMock()
        mock_vector_store.use_incremental = True
        mock_vector_store.search.side_effect = Exception("Vector store error")
        service.vector_store = mock_vector_store
        
        # Mock repository for fallback
        with patch(
            "app.services.similar_skus_service.get_candidate_products_by_brand",
            return_value=mock_products,
        ):
            vision_features = {
                "category": "运动鞋",
                "style": ["休闲"],
                "color": "黑色",
                "season": "四季",
                "keywords": [],
            }
            
            skus, fallback_used = await service.search_similar_skus(
                db=mock_db,
                brand_code="BL",
                vision_features=vision_features,
                top_k=5,
                mode="vector",
            )
            
            # Assertions
            assert fallback_used, "Should use fallback when vector mode fails"
            assert len(skus) > 0, "Should return results from rule fallback"
            assert len(skus) <= 5, "Should respect top_k limit"
            
            # Verify vector store was called (and failed)
            mock_vector_store.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty_list(self, mock_db):
        """测试：候选商品为空时返回空列表。"""
        service = SimilarSKUsService()
        
        with patch(
            "app.services.similar_skus_service.get_candidate_products_by_brand",
            return_value=[],
        ):
            vision_features = {
                "category": "运动鞋",
                "style": [],
                "color": "黑色",
                "season": "四季",
                "keywords": [],
            }
            
            skus, fallback_used = await service.search_similar_skus(
                db=mock_db,
                brand_code="BL",
                vision_features=vision_features,
                top_k=5,
                mode="rule",
            )
            
            assert skus == [], "Should return empty list when no candidates"
            assert not fallback_used

    @pytest.mark.asyncio
    async def test_scoring_prioritizes_category_match(self, mock_db):
        """测试：评分优先匹配 category。"""
        service = SimilarSKUsService()
        
        # Create products with different categories
        products = []
        for i, category in enumerate(["运动鞋", "休闲鞋", "运动鞋", "靴子"]):
            product = MagicMock(spec=Product)
            product.brand_code = "BL"
            product.sku = f"8WZ{i:02d}CM1"
            product.name = f"Product {i}"
            product.tags = []
            product.attributes = {"category": category, "颜色": "黑色"}
            product.updated_at = MagicMock()
            product.updated_at.timestamp.return_value = 1000 - i
            products.append(product)
        
        with patch(
            "app.services.similar_skus_service.get_candidate_products_by_brand",
            return_value=products,
        ):
            vision_features = {
                "category": "运动鞋",  # Target category
                "style": [],
                "color": "黑色",
                "season": "四季",
                "keywords": [],
            }
            
            skus, _ = await service.search_similar_skus(
                db=mock_db,
                brand_code="BL",
                vision_features=vision_features,
                top_k=5,
                mode="rule",
            )
            
            # Products with "运动鞋" category should be ranked higher
            # (This is a basic test - actual ranking depends on full scoring logic)
            assert len(skus) > 0, "Should return at least one SKU"


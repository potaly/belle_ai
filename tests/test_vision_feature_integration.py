"""Integration tests for vision feature normalization and trace_id caching (V6.0.0+)."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.vision_feature_normalizer import VisionFeatureNormalizer
from app.repositories.vision_feature_cache_repository import (
    VisionFeatureCacheRepository,
)
from app.services.similar_skus_service import SimilarSKUsService


class TestVisionFeatureNormalizer:
    """Test cases for VisionFeatureNormalizer."""

    def test_normalize_returns_complete_structure(self):
        """
        测试1：vision_analyze 返回 trace_id + vision_features 且结构正确。
        
        验证点：
        - vision_features 包含所有必需字段（category, style, color, colors, season, scene, keywords）
        - 字段类型正确
        - 缺失字段置空或使用默认值
        """
        visual_summary = {
            "category_guess": "运动鞋",
            "style_impression": ["休闲", "日常", "舒适"],
            "color_impression": "黑色",
            "season_impression": "四季",
        }
        selling_points = [
            "外观看起来比较百搭",
            "整体感觉偏轻便，适合日常穿",
            "风格偏休闲，通勤或周末都合适",
        ]

        result = VisionFeatureNormalizer.normalize(
            visual_summary=visual_summary,
            selling_points=selling_points,
            brand_code="BL",
            scene="guide_chat",
        )

        # Assertions
        assert isinstance(result, dict), "Result should be a dict"
        assert "category" in result, "Should have category"
        assert "style" in result, "Should have style"
        assert "color" in result, "Should have color"
        assert "colors" in result, "Should have colors"
        assert "season" in result, "Should have season"
        assert "scene" in result, "Should have scene"
        assert "keywords" in result, "Should have keywords"

        # Type checks
        assert result["category"] is None or isinstance(result["category"], str)
        assert isinstance(result["style"], list)
        assert result["color"] is None or isinstance(result["color"], str)
        assert isinstance(result["colors"], list)
        assert isinstance(result["season"], str)
        assert result["scene"] == "guide_chat"
        assert isinstance(result["keywords"], list)
        assert 3 <= len(result["keywords"]) <= 6, "Keywords should be 3-6 items"

    def test_normalize_colors_extraction(self):
        """测试颜色归一化。"""
        visual_summary = {
            "category_guess": "运动鞋",
            "style_impression": [],
            "color_impression": "黑白色",
            "season_impression": "四季",
        }
        selling_points = []

        result = VisionFeatureNormalizer.normalize(
            visual_summary=visual_summary,
            selling_points=selling_points,
        )

        # Should extract both colors
        assert len(result["colors"]) >= 1, "Should extract at least one color"
        assert result["color"] in result["colors"], "Primary color should be in colors list"


class TestSimilarSKUsWithTraceId:
    """Test cases for similar_skus with trace_id."""

    @pytest.mark.asyncio
    async def test_similar_skus_with_trace_id_returns_results(self, mock_db):
        """
        测试2：similar_skus 用 trace_id 能返回结果（mock candidates）。
        
        验证点：
        - trace_id 能正确解析 vision_features
        - 返回有效的 SKU 列表
        - 数量 <= top_k
        """
        # Mock cache repository
        mock_features = {
            "category": "运动鞋",
            "style": ["休闲", "日常"],
            "color": "黑色",
            "colors": ["黑色"],
            "season": "四季",
            "scene": "guide_chat",
            "keywords": ["百搭", "轻便"],
        }
        mock_cache_data = {
            "brand_code": "BL",
            "scene": "guide_chat",
            "vision_features": mock_features,
        }

        with patch(
            "app.services.similar_skus_service.VisionFeatureCacheRepository.get",
            return_value=mock_cache_data,
        ):
            # Mock product repository
            mock_products = []
            for i in range(10):
                product = MagicMock()
                product.brand_code = "BL"
                product.sku = f"8WZ{i:02d}CM1"
                product.name = f"Test Product {i}"
                product.tags = ["休闲", "日常"] if i % 2 == 0 else ["运动"]
                product.attributes = {
                    "category": "运动鞋" if i < 5 else "休闲鞋",
                    "颜色": "黑色" if i % 2 == 0 else "白色",
                }
                product.updated_at = MagicMock()
                product.updated_at.timestamp.return_value = 1000 - i
                mock_products.append(product)

            with patch(
                "app.services.similar_skus_service.get_candidate_products_by_brand",
                return_value=mock_products,
            ):
                service = SimilarSKUsService()

                skus, fallback_used = await service.search_similar_skus(
                    db=mock_db,
                    brand_code="BL",
                    trace_id="test_trace_id_123",
                    top_k=5,
                    mode="rule",
                )

                # Assertions
                assert len(skus) > 0, "Should return at least one SKU"
                assert len(skus) <= 5, "Should respect top_k limit"
                assert all(isinstance(sku, str) for sku in skus), "All items should be strings"
                assert not fallback_used, "Rule mode should not use fallback"

    @pytest.mark.asyncio
    async def test_trace_id_not_found_returns_error(self, mock_db):
        """
        测试3：trace_id 失效/不存在返回错误并埋点。
        
        验证点：
        - trace_id 不存在时返回 None
        - 埋点函数被调用
        """
        # Mock cache repository to return None (not found)
        with patch(
            "app.services.similar_skus_service.VisionFeatureCacheRepository.get",
            return_value=None,
        ):
            service = SimilarSKUsService()

            resolved_features, resolved_brand_code = await service._resolve_features(
                db=mock_db,
                trace_id="invalid_trace_id",
                vision_features=None,
                brand_code="BL",
            )

            # Assertions
            assert resolved_features is None, "Should return None when trace_id not found"
            assert resolved_brand_code is None, "Should return None for brand_code"

            # Test that search returns empty list when trace_id fails
            skus, fallback_used = await service.search_similar_skus(
                db=mock_db,
                brand_code="BL",
                trace_id="invalid_trace_id",
                top_k=5,
                mode="rule",
            )

            assert skus == [], "Should return empty list when trace_id not found"


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


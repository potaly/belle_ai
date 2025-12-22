"""Tests for DataVersionCalculator."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.data_version_calculator import DataVersionCalculator


def test_data_version_stability():
    """Test that same data produces same data_version."""
    product_data = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": Decimal("398.00"),
        "image_url": "https://example.com/image.jpg",
        "on_sale": True,
        "tags": ["百搭", "舒适", "时尚"],
        "attributes": {"color": "白色", "material": "牛皮"},
    }
    
    # Calculate multiple times
    version1 = DataVersionCalculator.calculate_data_version(product_data)
    version2 = DataVersionCalculator.calculate_data_version(product_data)
    version3 = DataVersionCalculator.calculate_data_version(product_data)
    
    # All should be identical
    assert version1 == version2 == version3
    assert len(version1) == 32  # MD5 hash length


def test_data_version_includes_brand_code():
    """Test that brand_code is included in data_version calculation."""
    base_data = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": Decimal("398.00"),
    }
    
    # Same data with different brand_code should produce different version
    data1 = {**base_data, "brand_code": "BELLE"}
    data2 = {**base_data, "brand_code": "OTHER"}
    
    version1 = DataVersionCalculator.calculate_data_version(data1)
    version2 = DataVersionCalculator.calculate_data_version(data2)
    
    assert version1 != version2


def test_data_version_json_stable_serialization():
    """Test that JSON stable serialization works correctly."""
    # Test with different key orders (should produce same version)
    data1 = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": Decimal("398.00"),
        "tags": ["百搭", "舒适"],
        "attributes": {"color": "白色", "material": "牛皮"},
    }
    
    data2 = {
        "attributes": {"material": "牛皮", "color": "白色"},  # Different key order
        "tags": ["舒适", "百搭"],  # Different order
        "price": Decimal("398.00"),
        "name": "女士小白鞋",
        "sku": "8WZ01CM5",
        "brand_code": "BELLE",
    }
    
    version1 = DataVersionCalculator.calculate_data_version(data1)
    version2 = DataVersionCalculator.calculate_data_version(data2)
    
    # Should produce same version despite different key/order
    assert version1 == version2


def test_data_version_price_decimal_not_float():
    """Test that price uses Decimal/str, not float."""
    # Test with Decimal
    data1 = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": Decimal("398.00"),
    }
    
    # Test with str (should produce same version as Decimal)
    data2 = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": "398.00",
    }
    
    version1 = DataVersionCalculator.calculate_data_version(data1)
    version2 = DataVersionCalculator.calculate_data_version(data2)
    
    # Should produce same version
    assert version1 == version2
    
    # Test with float (should be converted to string)
    data3 = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": 398.0,  # float
    }
    
    version3 = DataVersionCalculator.calculate_data_version(data3)
    # Float should be converted to string, may or may not match exactly
    assert isinstance(version3, str)
    assert len(version3) == 32


def test_data_version_list_deduplication():
    """Test that lists are deduplicated and sorted."""
    data1 = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": Decimal("398.00"),
        "tags": ["百搭", "舒适", "百搭"],  # Duplicate
    }
    
    data2 = {
        "brand_code": "BELLE",
        "sku": "8WZ01CM5",
        "name": "女士小白鞋",
        "price": Decimal("398.00"),
        "tags": ["舒适", "百搭"],  # No duplicate, different order
    }
    
    version1 = DataVersionCalculator.calculate_data_version(data1)
    version2 = DataVersionCalculator.calculate_data_version(data2)
    
    # Should produce same version (deduplicated and sorted)
    assert version1 == version2


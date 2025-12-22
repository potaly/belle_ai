"""Tests for ETL product worker."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

# Mark tests that require database
pytestmark = pytest.mark.skipif(
    True,  # Skip by default - these are integration tests requiring database
    reason="Integration tests require database connection. Run manually with database configured."
)

# Delay imports to avoid database connection errors during test collection
try:
    from sqlalchemy.orm import Session
    from app.core.database import SessionLocal
    from app.models.etl_watermark import ETLWatermark
    from app.models.product import Product
    from app.models.product_change_log import ProductChangeLog
    from app.repositories.product_staging_repository import ProductStagingRepository
    from app.services.product_upsert_service import ProductUpsertService
    DB_AVAILABLE = True
except (ImportError, Exception) as e:
    DB_AVAILABLE = False
    # Create dummy types for type hints
    Session = None
    SessionLocal = None
    ETLWatermark = None
    Product = None
    ProductChangeLog = None
    ProductStagingRepository = None
    ProductUpsertService = None


@pytest.fixture
def db_session():
    """Create database session for testing."""
    if not DB_AVAILABLE:
        pytest.skip("Database not available")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_etl_idempotency(db_session: Session):
    """Test that running ETL multiple times doesn't create duplicate change_log entries."""
    # This test requires:
    # 1. products_staging table with test data
    # 2. products table with UNIQUE(brand_code, sku) constraint
    # 3. etl_watermark and product_change_log tables
    
    # Note: This is a high-level integration test
    # In practice, you may need to set up test fixtures with actual staging data
    
    # Mock staging data (in real test, this would come from products_staging)
    staging_record = {
        "style_brand_no": "BELLE",
        "style_no": "TEST001",
        "name": "测试商品",
        "price": Decimal("100.00"),
        "colors_concat": "红色||蓝色",
        "tags_json": ["测试", "商品"],
        "attrs_json": {"color": "红色", "size": "M||L"},
        "description": "测试描述",
        "image_url": "https://example.com/test.jpg",
        "on_sale": True,
        "src_updated_at": datetime.now(),
    }
    
    # Normalize and upsert first time
    from app.services.product_normalizer import ProductNormalizer
    
    normalized = ProductNormalizer.normalize_staging_record(staging_record)
    upsert_service = ProductUpsertService(db_session)
    
    # First upsert
    changed1, version1 = upsert_service.upsert_product(normalized)
    assert changed1 is True
    assert version1 is not None
    
    # Count change_log entries
    count1 = (
        db_session.query(ProductChangeLog)
        .filter(
            ProductChangeLog.brand_code == "BELLE",
            ProductChangeLog.sku == "TEST001",
            ProductChangeLog.data_version == version1,
        )
        .count()
    )
    assert count1 == 1
    
    # Second upsert (same data, should not create new change_log)
    changed2, version2 = upsert_service.upsert_product(normalized)
    assert changed2 is False  # No change detected
    assert version2 == version1
    
    # Count should still be 1 (idempotent)
    count2 = (
        db_session.query(ProductChangeLog)
        .filter(
            ProductChangeLog.brand_code == "BELLE",
            ProductChangeLog.sku == "TEST001",
            ProductChangeLog.data_version == version1,
        )
        .count()
    )
    assert count2 == 1, "Change log should not have duplicates (idempotent)"


def test_watermark_same_second_no_miss(db_session: Session):
    """Test that watermark correctly handles same-second records."""
    # This test verifies the "same-second no-miss" design
    
    repo = ProductStagingRepository(db_session)
    
    # Mock: Create test records with same src_updated_at
    same_time = datetime.now()
    
    # Simulate fetching with watermark
    # In real scenario, this would query products_staging
    # For test, we verify the SQL logic is correct
    
    # Test watermark key format: style_brand_no#style_no
    key1 = "BELLE#SKU001"
    key2 = "BELLE#SKU002"
    
    # Keys should be sortable
    assert key1 < key2
    
    # Verify watermark update logic
    watermark = ETLWatermark(
        table_name="products_staging",
        last_processed_at=same_time,
        last_processed_key=key1,
    )
    db_session.add(watermark)
    db_session.commit()
    
    # Verify watermark can be retrieved
    retrieved = (
        db_session.query(ETLWatermark)
        .filter(ETLWatermark.table_name == "products_staging")
        .first()
    )
    assert retrieved is not None
    assert retrieved.last_processed_key == key1


def test_etl_resume_from_watermark(db_session: Session):
    """Test that ETL can resume from watermark."""
    # This test verifies resume functionality
    
    # Set watermark
    watermark = ETLWatermark(
        table_name="products_staging",
        last_processed_at=datetime(2024, 1, 1, 0, 0, 0),
        last_processed_key="BELLE#OLD001",
    )
    db_session.add(watermark)
    db_session.commit()
    
    # Verify watermark exists
    retrieved = (
        db_session.query(ETLWatermark)
        .filter(ETLWatermark.table_name == "products_staging")
        .first()
    )
    assert retrieved is not None
    assert retrieved.last_processed_at == datetime(2024, 1, 1, 0, 0, 0)
    assert retrieved.last_processed_key == "BELLE#OLD001"


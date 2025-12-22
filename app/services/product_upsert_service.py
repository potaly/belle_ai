"""Product upsert service with change log tracking."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.product_change_log import ChangeStatus, ChangeType
from app.repositories.product_repository import (
    get_product_by_brand_and_sku,
    upsert_product_by_brand_and_sku,
)
from app.services.data_version_calculator import DataVersionCalculator

logger = logging.getLogger(__name__)


class ProductUpsertService:
    """Service for upserting products with change log tracking."""

    def __init__(self, db: Session):
        """
        Initialize service.
        
        Args:
            db: Database session
        """
        self.db = db

    def upsert_product(
        self, normalized_data: dict[str, Any]
    ) -> tuple[bool, str | None]:
        """
        Upsert product with change detection.
        
        Rules:
        - Calculate data_version from normalized_data
        - Check if product exists and compare data_version
        - Only update if data_version changed
        - Write change_log only if data_version changed
        - Use INSERT ... ON DUPLICATE KEY UPDATE (via repository)
        
        Args:
            normalized_data: Normalized product data dictionary
            
        Returns:
            Tuple of (changed: bool, data_version: str | None)
        """
        brand_code = normalized_data["brand_code"]
        sku = normalized_data["sku"]
        
        logger.info(
            f"[UPSERT_SERVICE] Processing: brand_code={brand_code}, sku={sku}"
        )
        
        # Calculate new data_version
        new_data_version = DataVersionCalculator.calculate_data_version(
            normalized_data
        )
        
        # Check if product exists
        existing_product = get_product_by_brand_and_sku(self.db, brand_code, sku)
        
        if existing_product:
            # Product exists: check if data_version changed
            # Note: We need to calculate existing product's data_version
            existing_data = {
                "brand_code": existing_product.brand_code,
                "sku": existing_product.sku,
                "name": existing_product.name,
                "price": existing_product.price,
                "image_url": existing_product.image_url,
                "tags": existing_product.tags,
                "attributes": existing_product.attributes,
            }
            
            # Add on_sale if exists in model
            if hasattr(existing_product, "on_sale"):
                existing_data["on_sale"] = existing_product.on_sale
            
            existing_data_version = DataVersionCalculator.calculate_data_version(
                existing_data
            )
            
            if existing_data_version == new_data_version:
                # No change: skip update
                logger.info(
                    f"[UPSERT_SERVICE] No change detected: "
                    f"brand_code={brand_code}, sku={sku}, version={new_data_version}"
                )
                return False, new_data_version
            
            # Data changed: update product
            change_type = ChangeType.UPDATE.value
            logger.info(
                f"[UPSERT_SERVICE] Data changed: "
                f"brand_code={brand_code}, sku={sku}, "
                f"old_version={existing_data_version}, new_version={new_data_version}"
            )
        else:
            # Product does not exist: create
            change_type = ChangeType.CREATE.value
            logger.info(
                f"[UPSERT_SERVICE] Creating new product: "
                f"brand_code={brand_code}, sku={sku}, version={new_data_version}"
            )
        
        # Upsert product (using INSERT ... ON DUPLICATE KEY UPDATE)
        upsert_product_by_brand_and_sku(self.db, normalized_data)
        
        # Write change_log (with unique constraint to prevent duplicates)
        self._write_change_log(brand_code, sku, new_data_version, change_type)
        
        return True, new_data_version

    def _write_change_log(
        self, brand_code: str, sku: str, data_version: str, change_type: str
    ) -> None:
        """
        Write change log entry (idempotent).
        
        Uses INSERT IGNORE or INSERT ... ON DUPLICATE KEY UPDATE to prevent duplicates.
        
        Args:
            brand_code: Brand code
            sku: SKU
            data_version: Data version hash
            change_type: Change type (CREATE/UPDATE/DELETE)
        """
        from app.models.product_change_log import ProductChangeLog
        
        # Try to insert (will fail silently if duplicate due to unique constraint)
        try:
            change_log = ProductChangeLog(
                brand_code=brand_code,
                sku=sku,
                data_version=data_version,
                status=ChangeStatus.PENDING.value,
                change_type=change_type,
            )
            self.db.add(change_log)
            self.db.commit()
            logger.debug(
                f"[UPSERT_SERVICE] Change log written: "
                f"brand_code={brand_code}, sku={sku}, version={data_version}"
            )
        except Exception as e:
            # Unique constraint violation: already exists (idempotent)
            self.db.rollback()
            logger.debug(
                f"[UPSERT_SERVICE] Change log already exists (idempotent): "
                f"brand_code={brand_code}, sku={sku}, version={data_version}, error={e}"
            )


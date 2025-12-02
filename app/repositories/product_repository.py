"""Product repository for database access."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.product import Product

logger = logging.getLogger(__name__)


def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    """
    Get product by SKU.
    
    Args:
        db: Database session
        sku: Product SKU identifier
        
    Returns:
        Product instance if found, None otherwise
    """
    logger.info(f"[REPOSITORY] Querying product by SKU: {sku}")
    product = db.query(Product).filter(Product.sku == sku).first()
    if product:
        logger.info(f"[REPOSITORY] ✓ Product found: id={product.id}, name={product.name}, price={product.price}, tags={product.tags}")
    else:
        logger.warning(f"[REPOSITORY] ✗ Product not found: sku={sku}")
    return product


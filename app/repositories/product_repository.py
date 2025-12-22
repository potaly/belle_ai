"""Product repository for database access."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.product import Product

logger = logging.getLogger(__name__)


def get_product_by_sku(db: Session, sku: str) -> Optional[Product]:
    """
    Get product by SKU.
    
    ⚠️ Warning: This method only queries by sku, which may return incorrect results
    if the same sku exists under different brand_code. Use get_product_by_brand_and_sku
    for ETL operations.
    
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


def get_product_by_brand_and_sku(
    db: Session, brand_code: str, sku: str
) -> Optional[Product]:
    """
    Get product by brand_code and sku (business primary key).
    
    Args:
        db: Database session
        brand_code: Brand code
        sku: Product SKU identifier
        
    Returns:
        Product instance if found, None otherwise
    """
    logger.info(f"[REPOSITORY] Querying product by brand_code={brand_code}, sku={sku}")
    product = (
        db.query(Product)
        .filter(Product.brand_code == brand_code, Product.sku == sku)
        .first()
    )
    if product:
        logger.info(
            f"[REPOSITORY] ✓ Product found: id={product.id}, "
            f"brand_code={product.brand_code}, sku={product.sku}, name={product.name}"
        )
    else:
        logger.warning(f"[REPOSITORY] ✗ Product not found: brand_code={brand_code}, sku={sku}")
    return product


def upsert_product_by_brand_and_sku(
    db: Session, product_data: dict[str, Any]
) -> Product:
    """
    Upsert product by (brand_code, sku) using INSERT ... ON DUPLICATE KEY UPDATE.
    
    Rules:
    - Uses MySQL INSERT ... ON DUPLICATE KEY UPDATE
    - Does NOT overwrite id / created_at fields
    - Updates updated_at to current timestamp
    
    Args:
        db: Database session
        product_data: Product data dictionary with keys:
            - brand_code: str (required)
            - sku: str (required)
            - name: str (required)
            - price: Decimal or str (required)
            - tags: list or None
            - attributes: dict or None
            - description: str or None
            - image_url: str or None
            - on_sale: bool or None (if exists in model)
    
    Returns:
        Product instance (created or updated)
    """
    brand_code = product_data["brand_code"]
    sku = product_data["sku"]
    
    logger.info(f"[REPOSITORY] Upserting product: brand_code={brand_code}, sku={sku}")
    
    # Check if on_sale column exists in products table
    # Query table structure to determine available columns
    result = db.execute(text("SHOW COLUMNS FROM products"))
    available_columns = {row.Field for row in result}
    
    # Use MySQL INSERT ... ON DUPLICATE KEY UPDATE (as required)
    # Build field list (exclude id, created_at from update)
    insert_fields = [
        "brand_code", "sku", "name", "price", "tags", "attributes",
        "description", "image_url"
    ]
    
    # Add on_sale only if it exists in table AND is provided in data
    if "on_sale" in product_data and "on_sale" in available_columns:
        insert_fields.append("on_sale")
    
    # Build SQL with JSON handling
    field_names = ", ".join(insert_fields)
    placeholders = ", ".join([f":{field}" for field in insert_fields])
    
    # Update clause: update all fields except brand_code, sku (and id, created_at are auto-handled)
    update_fields = [f for f in insert_fields if f not in ("brand_code", "sku")]
    update_clause = ", ".join([
        f"{field} = VALUES({field})" for field in update_fields
    ])
    update_clause += ", updated_at = NOW()"
    
    sql = f"""
    INSERT INTO products ({field_names}, updated_at)
    VALUES ({placeholders}, NOW())
    ON DUPLICATE KEY UPDATE {update_clause}
    """
    
    # Prepare values (handle JSON fields)
    import json
    values = {}
    for field in insert_fields:
        value = product_data.get(field)
        # Convert dict/list to JSON string for MySQL JSON column
        # MySQL JSON type accepts JSON string or native Python dict/list (SQLAlchemy handles it)
        # For raw SQL, we need to pass as JSON string
        if field in ("tags", "attributes") and value is not None:
            if isinstance(value, (dict, list)):
                # Convert to JSON string for raw SQL
                values[field] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, str):
                # Already a JSON string, validate it
                try:
                    json.loads(value)  # Validate JSON
                    values[field] = value
                except json.JSONDecodeError:
                    logger.warning(f"[REPOSITORY] Invalid JSON string for {field}: {value}")
                    values[field] = None
            else:
                values[field] = value
        else:
            values[field] = value
    
    # Execute
    db.execute(text(sql), values)
    db.commit()
    
    # Fetch the product
    product = get_product_by_brand_and_sku(db, brand_code, sku)
    if not product:
        raise RuntimeError(f"Failed to upsert product: brand_code={brand_code}, sku={sku}")
    
    logger.info(f"[REPOSITORY] ✓ Product upserted: id={product.id}")
    return product


"""Product repository for database access."""
from __future__ import annotations

import logging
from typing import Any, List, Optional

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


def get_candidate_products_by_brand(
    db: Session,
    brand_code: str,
    category: Optional[str] = None,
    limit: int = 300,
    check_on_sale: bool = True,
) -> List[Product]:
    """
    获取候选商品列表（用于相似度检索）。
    
    业务规则：
    1. 必选过滤：brand_code = input.brand_code
    2. 可选过滤：category 精确匹配（如果提供）
    3. on_sale 过滤：如果表中有 on_sale 字段且 check_on_sale=True
    4. 限制数量：limit（默认300，避免全表扫描）
    5. 排序：按 updated_at desc 或 id desc
    
    Args:
        db: Database session
        brand_code: Brand code (required)
        category: Category filter (optional)
        limit: Maximum number of candidates (default 300)
        check_on_sale: Whether to filter by on_sale=1 (default True)
    
    Returns:
        List of Product instances
    """
    logger.info(
        f"[REPOSITORY] Querying candidate products: brand_code={brand_code}, "
        f"category={category}, limit={limit}, check_on_sale={check_on_sale}"
    )
    
    query = db.query(Product).filter(Product.brand_code == brand_code)
    
    # Category filter (if provided)
    # Note: Product model doesn't have category column, we'll filter in Python
    # This is handled in the service layer after fetching candidates
    
    # on_sale filter (if column exists and check_on_sale=True)
    if check_on_sale:
        try:
            # Check if on_sale column exists
            result = db.execute(text("SHOW COLUMNS FROM products LIKE 'on_sale'"))
            if result.fetchone():
                query = query.filter(text("on_sale = 1"))
                logger.debug("[REPOSITORY] Applied on_sale=1 filter")
        except Exception as e:
            logger.debug(f"[REPOSITORY] on_sale column check failed: {e}, skipping filter")
    
    # Order by updated_at desc (or id desc as fallback)
    try:
        query = query.order_by(Product.updated_at.desc())
    except AttributeError:
        query = query.order_by(Product.id.desc())
    
    # Limit
    products = query.limit(limit).all()
    
    # Log sample product info for debugging (after products is fetched)
    if products:
        sample_product = products[0]
        logger.debug(
            f"[REPOSITORY] Sample product: sku={sample_product.sku}, "
            f"name={sample_product.name[:50] if sample_product.name else 'N/A'}, "
            f"tags={sample_product.tags}, "
            f"attributes_keys={list(sample_product.attributes.keys()) if sample_product.attributes else []}"
        )
    
    # If category filter was not applied at DB level, filter in Python
    if category:
        filtered_products = []
        for product in products:
            # Check category from column or attributes
            product_category = None
            if hasattr(product, "category") and product.category:
                product_category = product.category
            elif product.attributes:
                product_category = product.attributes.get("category") or product.attributes.get("类目")
            
            if product_category and category in str(product_category):
                filtered_products.append(product)
        
        products = filtered_products
        logger.debug(f"[REPOSITORY] Filtered by category in Python: {len(products)} products")
    
    logger.info(f"[REPOSITORY] ✓ Found {len(products)} candidate products")
    return products


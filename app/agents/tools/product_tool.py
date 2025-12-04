"""Product tool for fetching product information."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.models.product import Product
from app.repositories.product_repository import get_product_by_sku

logger = logging.getLogger(__name__)


async def fetch_product(
    context: AgentContext,
    db: Session,
    **kwargs: Any,
) -> AgentContext:
    """
    获取商品信息并添加到上下文。
    
    调用逻辑：
    - 通常在规划器生成的计划中作为第一步执行（fetch_product）
    - 前提条件：context.sku 必须已设置
    - 调用场景：AgentRunner 执行计划时，或手动调用以加载商品数据
    - 调用后：context.product 被填充，后续工具（如 RAG、Copy）依赖此数据
    
    This tool loads a product from the database using the SKU from context,
    and updates context.product with the loaded product.
    
    Args:
        context: Agent context (must have sku set)
        db: Database session
        **kwargs: Additional arguments (ignored)
    
    Returns:
        Updated AgentContext with product loaded
    
    Raises:
        HTTPException: If SKU is missing or product not found
    
    Example:
        >>> context = AgentContext(sku="8WZ01CM1")
        >>> context = await fetch_product(context, db)
        >>> print(context.product.name)
        '舒适跑鞋'
    """
    logger.info("=" * 80)
    logger.info("[PRODUCT_TOOL] Fetching product information")
    logger.info(f"[PRODUCT_TOOL] Context SKU: {context.sku}")
    
    if not context.sku:
        error_msg = "SKU is required in context to fetch product"
        logger.error(f"[PRODUCT_TOOL] ✗ {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    
    try:
        # Load product from database
        product = get_product_by_sku(db, context.sku)
        
        if not product:
            error_msg = f"Product with SKU {context.sku} not found"
            logger.error(f"[PRODUCT_TOOL] ✗ {error_msg}")
            raise HTTPException(status_code=404, detail=error_msg)
        
        # Update context with product
        context.product = product
        
        logger.info(
            f"[PRODUCT_TOOL] ✓ Product loaded: id={product.id}, "
            f"name={product.name}, price={product.price}"
        )
        logger.info("=" * 80)
        
        return context
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"[PRODUCT_TOOL] ✗ Error fetching product: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch product: {str(e)}"
        )


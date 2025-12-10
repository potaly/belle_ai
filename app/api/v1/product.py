"""Product analysis API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.product_repository import get_product_by_sku
from app.schemas.product_schemas import (
    ProductAnalysisRequest,
    ProductAnalysisResponse,
)
from app.services.product_service import analyze_product

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze/product", response_model=ProductAnalysisResponse)
async def analyze_product_endpoint(
    request: ProductAnalysisRequest,
    db: Session = Depends(get_db),
) -> ProductAnalysisResponse:   
    """
    分析产品并返回结构化卖点。

    本接口通过基于规则的逻辑，根据产品标签和属性生成产品分析结果。

    参数说明:
        request: 产品分析请求体，包含 SKU
        db: 数据库会话
        
    返回值:
        ProductAnalysisResponse，包含核心卖点、风格标签、适用场景建议、适合人群、解决的痛点等
    """

    logger.info("=" * 80)
    logger.info("[API] POST /ai/analyze/product - Request received")
    logger.info(f"[API] Request parameters: sku={request.sku}")
    
    try:
        # Validate product exists
        logger.info("[API] Step 1: Validating product exists...")
        product = get_product_by_sku(db, request.sku)
        if not product:
            logger.warning(f"[API] Product not found: sku={request.sku}")
            raise HTTPException(
                status_code=404, detail=f"Product with SKU {request.sku} not found"
            )
        logger.info(f"[API] ✓ Product found: name={product.name}, sku={product.sku}")
        
        # Analyze product using rule-based logic
        logger.info("[API] Step 2: Analyzing product...")
        result = analyze_product(product)
        
        logger.info("[API] ✓ Analysis completed successfully")
        logger.info(f"[API] Response: core_selling_points={len(result.core_selling_points)}, "
                   f"style_tags={len(result.style_tags)}, "
                   f"scene_suggestion={len(result.scene_suggestion)}")
        logger.info("=" * 80)
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        logger.info("=" * 80)
        raise
    except Exception as e:
        logger.error(f"[API] ✗ Unexpected error in analyze_product endpoint: {e}", exc_info=True)
        logger.info("=" * 80)
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze product: {str(e)}"
        )


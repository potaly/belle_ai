"""Copy generation API endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.copy_schemas import CopyRequest, CopyStyle
from app.services.copy_service import generate_copy_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate/copy")
async def generate_copy(
    request: CopyRequest,
    db: Session = Depends(get_db),
    guide_id: str | None = None,
) -> StreamingResponse:
    """
    Generate WeChat Moments copy for a product (streaming).
    
    This endpoint streams copy generation in real-time using Server-Sent Events (SSE).
    The first chunk is emitted within 500ms.
    
    Args:
        request: Copy generation request
        db: Database session
        guide_id: Guide ID (optional, can be extracted from headers/auth)
        
    Returns:
        StreamingResponse with SSE format
    """
    logger.info("=" * 80)
    logger.info("[API] POST /ai/generate/copy - Request received")
    logger.info(f"[API] Request parameters: sku={request.sku}, style={request.style.value}, guide_id={guide_id}")
    logger.info(f"[API] Request body: {request.model_dump()}")
    
    # Validate product exists BEFORE creating stream
    # This ensures we can return proper HTTP error before streaming starts
    from app.repositories.product_repository import get_product_by_sku
    
    logger.info("[API] Step 1: Validating product exists...")
    product = get_product_by_sku(db, request.sku)
    if not product:
        logger.warning(f"[API] Product not found: sku={request.sku}")
        raise HTTPException(status_code=404, detail=f"Product with SKU {request.sku} not found")
    logger.info(f"[API] ✓ Product found: name={product.name}, sku={product.sku}")
    
    try:
        logger.info("[API] Step 2: Creating streaming response...")
        # Generate streaming response
        stream = generate_copy_stream(
            db=db,
            sku=request.sku,
            style=request.style,
            guide_id=guide_id,
        )
        
        logger.info("[API] Step 3: Returning StreamingResponse")
        logger.info("[API] ✓ Request processed successfully, streaming started")
        logger.info("=" * 80)
        
        return StreamingResponse(
            stream,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions (like 404)
        logger.error(f"[API] ✗ HTTPException: status={e.status_code}, detail={e.detail}")
        logger.info("=" * 80)
        raise
    except Exception as e:
        logger.error(f"[API] ✗ Unexpected error in generate_copy endpoint: {e}", exc_info=True)
        logger.info("=" * 80)
        raise HTTPException(status_code=500, detail=f"Failed to generate copy: {str(e)}")


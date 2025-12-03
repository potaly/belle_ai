"""Service for copy generation."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import AsyncGenerator, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.product_repository import get_product_by_sku
from app.schemas.copy_schemas import CopyStyle
from app.services.log_service import log_ai_task
from app.services.streaming_generator import StreamingGenerator
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)


async def generate_copy_stream(
    db: Session,
    sku: str,
    style: CopyStyle = CopyStyle.natural,
    guide_id: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Generate streaming copy for a product.
    
    Args:
        db: Database session
        sku: Product SKU
        style: Copy style
        guide_id: Guide ID (optional)
        
    Yields:
        Streaming response chunks
        
    Raises:
        HTTPException: If product not found
    """
    start_time = time.time()
    task_id = str(uuid.uuid4())
    
    logger.info(f"[SERVICE] ========== Copy Generation Service Started ==========")
    logger.info(f"[SERVICE] Task ID: {task_id}")
    logger.info(f"[SERVICE] Input parameters: sku={sku}, style={style.value}, guide_id={guide_id}")
    
    # Load product from repository BEFORE starting stream
    # This ensures we fail fast if product doesn't exist
    logger.info(f"[SERVICE] Step 1: Loading product from database (sku={sku})...")
    product = get_product_by_sku(db, sku)
    if not product:
        logger.error(f"[SERVICE] ✗ Product not found: sku={sku}")
        # Raise exception before any streaming starts
        raise HTTPException(status_code=404, detail=f"Product with SKU {sku} not found")
    logger.info(f"[SERVICE] ✓ Product loaded: id={product.id}, name={product.name}, tags={product.tags}")
    
    try:
        # Prepare input data for logging
        input_data = {
            "sku": sku,
            "product_name": product.name,
            "tags": product.tags,
            "style": style.value,
        }
        logger.info(f"[SERVICE] Step 2: Prepared input data: {json.dumps(input_data, ensure_ascii=False, indent=2)}")
        
        # Generate streaming content
        logger.info(f"[SERVICE] Step 3: Initializing StreamingGenerator...")
        generator = StreamingGenerator()
        posts = []
        
        logger.info(f"[SERVICE] Step 4: Starting streaming generation (calling generator)...")
        chunk_count = 0
        # Stream and collect posts
        async for chunk in generator.generate_copy_stream(product, style):
            chunk_count += 1
            if chunk_count <= 3:  # Log first few chunks
                logger.debug(f"[SERVICE] Chunk #{chunk_count}: {chunk[:100]}...")
            yield chunk
            
            # Parse chunk to collect posts (for logging)
            # Extract posts from post_end chunks
            if chunk.startswith("data: "):
                try:
                    chunk_data = json.loads(chunk[6:].strip())
                    if chunk_data.get("type") == "post_end":
                        posts.append(chunk_data.get("content", ""))
                        logger.info(f"[SERVICE] ✓ Post #{chunk_data.get('index')} completed: {chunk_data.get('content', '')[:50]}...")
                except:
                    pass  # Ignore parsing errors during streaming
        
        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"[SERVICE] Step 5: Streaming completed. Total chunks: {chunk_count}, Latency: {latency_ms}ms")
        logger.info(f"[SERVICE] Generated {len(posts)} posts")
        
        # Log task asynchronously (fire and forget)
        llm_client = get_llm_client()
        model_name = llm_client.settings.llm_model if (llm_client.settings.llm_api_key and llm_client.settings.llm_base_url) else "template-fallback"
        
        output_data = {
            "task_id": task_id,
            "latency_ms": latency_ms,
            "posts_count": len(posts),
            "posts": posts,
        }
        logger.info(f"[SERVICE] Step 6: Logging task to database (async)...")
        logger.info(f"[SERVICE] Output data: {json.dumps(output_data, ensure_ascii=False, indent=2)}")
        
        asyncio.create_task(
            log_ai_task(
                scene_type="copy",
                input_data=input_data,
                output_result=output_data,
                guide_id=guide_id,
                model_name=model_name,
                latency_ms=latency_ms,
                task_id=task_id,
            )
        )
        logger.info(f"[SERVICE] ✓ Task logging initiated (async)")
        logger.info(f"[SERVICE] ========== Copy Generation Service Completed ==========")
        
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        logger.error(f"[SERVICE] ✗ HTTPException raised")
        raise
    except Exception as e:
        logger.error(f"[SERVICE] ✗ Error generating copy: {e}", exc_info=True)
        # Only raise if stream hasn't started
        # If stream has started, we can't raise HTTPException anymore
        # So we log the error and let the stream complete
        raise HTTPException(status_code=500, detail="Failed to generate copy")

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
from app.services.llm_client import get_llm_client, LLMClientError
from app.services.prompt_builder import PromptBuilder
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


def prepare_copy_generation(
    db: Session,
    sku: str,
    style: CopyStyle = CopyStyle.natural,
) -> tuple[Product, str, int, bool, list[str], str]:
    """
    Prepare copy generation: load product, retrieve RAG context, build prompt.
    
    Returns:
        Tuple of (product, prompt, prompt_tokens, rag_used, rag_context, model_name)
    """
    logger.info(f"[SERVICE] ========== Copy Generation Preparation ==========")
    logger.info(f"[SERVICE] Input parameters: sku={sku}, style={style.value}")
    
    # Step 1: Load product
    logger.info(f"[SERVICE] Step 1: Loading product from database (sku={sku})...")
    product = get_product_by_sku(db, sku)
    if not product:
        logger.error(f"[SERVICE] ✗ Product not found: sku={sku}")
        raise HTTPException(status_code=404, detail=f"Product with SKU {sku} not found")
    logger.info(f"[SERVICE] ✓ Product loaded: id={product.id}, name={product.name}, tags={product.tags}")
    
    # Step 2: Retrieve RAG context
    logger.info(f"[SERVICE] Step 2: Retrieving RAG context...")
    rag_service = get_rag_service()
    rag_context = []
    rag_used = False
    
    if rag_service.is_available():
        # Build query from product information
        query_parts = [product.name]
        if product.tags:
            query_parts.extend(product.tags[:3])  # Use top 3 tags
        query = " ".join(query_parts)
        
        rag_context = rag_service.retrieve_context(query, top_k=3)
        rag_used = len(rag_context) > 0
        logger.info(f"[SERVICE] ✓ RAG context retrieved: {len(rag_context)} chunks, used={rag_used}")
    else:
        logger.warning(f"[SERVICE] RAG service not available, skipping context retrieval")
    
    # Step 3: Build prompt
    logger.info(f"[SERVICE] Step 3: Building prompt...")
    prompt_builder = PromptBuilder()
    prompt = prompt_builder.build_copy_prompt(product, style, rag_context if rag_used else None)
    
    # Estimate tokens
    prompt_tokens = prompt_builder.estimate_tokens(prompt)
    logger.info(f"[SERVICE] ✓ Prompt built: {len(prompt)} chars, ~{prompt_tokens} tokens")
    
    # Get model name
    llm_client = get_llm_client()
    model_name = llm_client.settings.llm_model if (llm_client.settings.llm_api_key and llm_client.settings.llm_base_url) else "template-fallback"
    
    logger.info(f"[SERVICE] ========== Preparation Completed ==========")
    
    return product, prompt, prompt_tokens, rag_used, rag_context, model_name

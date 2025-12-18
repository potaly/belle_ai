"""Service for private-chat sales copy generation (V5.3.0+).

重构说明：
- 从"营销广告"升级为"导购 1v1 私聊促单话术"
- 语气自然、非营销
- 根据 intent_level 使用不同策略
- 包含降级机制（LLM 失败时使用规则模板）
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import AsyncGenerator, Dict, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.product import Product
from app.repositories.product_repository import get_product_by_sku
from app.schemas.copy_schemas import CopyStyle
from app.services.fallback_copy import generate_fallback_copy
from app.services.log_service import log_ai_task
from app.services.llm_client import LLMClientError, get_llm_client
from app.services.prompt_templates import (
    build_system_prompt,
    build_user_prompt,
    validate_copy_output,
)
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


async def generate_private_chat_copy(
    db: Session,
    sku: str,
    intent_level: str,
    intent_reason: str,
    behavior_summary: Optional[Dict] = None,
    max_length: Optional[int] = None,
) -> tuple[str, bool, str]:
    """
    生成导购 1v1 私聊促单话术（生产环境安全可控）。
    
    业务规则：
    - 语气自然、非营销
    - 根据 intent_level 使用不同策略
    - 包含轻量行动建议
    - LLM 失败时使用降级模板
    
    Args:
        db: Database session
        sku: Product SKU
        intent_level: Intent level (high/hesitating/medium/low)
        intent_reason: Intent classification reason
        behavior_summary: Behavior summary (optional)
        max_length: Maximum length (default from config)
    
    Returns:
        Tuple of (copy_text, llm_used, strategy_used)
        - copy_text: Generated copy
        - llm_used: Whether LLM was used (True) or fallback (False)
        - strategy_used: Strategy description
    """
    logger.info(
        f"[COPY_SERVICE] ========== Private Chat Copy Generation =========="
    )
    logger.info(
        f"[COPY_SERVICE] Input: sku={sku}, intent={intent_level}, "
        f"reason={intent_reason[:50]}..."
    )
    
    # 获取配置
    settings = get_settings()
    max_length = max_length or settings.copy_max_length
    
    # Step 1: Load product
    logger.info(f"[COPY_SERVICE] Step 1: Loading product (sku={sku})...")
    product = get_product_by_sku(db, sku)
    if not product:
        logger.error(f"[COPY_SERVICE] ✗ Product not found: sku={sku}")
        raise HTTPException(status_code=404, detail=f"Product with SKU {sku} not found")
    logger.info(f"[COPY_SERVICE] ✓ Product loaded: {product.name}")
    
    # Step 2: Try LLM generation
    llm_used = False
    copy_text = None
    strategy_used = _get_strategy_description(intent_level)
    
    try:
        logger.info(f"[COPY_SERVICE] Step 2: Attempting LLM generation...")
        
        # Build prompts
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(
            product=product,
            intent_level=intent_level,
            intent_reason=intent_reason,
            behavior_summary=behavior_summary,
            max_length=max_length,
        )
        
        # Call LLM
        llm_client = get_llm_client()
        if llm_client.settings.llm_api_key and llm_client.settings.llm_base_url:
            logger.info(f"[COPY_SERVICE] Calling LLM: {llm_client.settings.llm_model}")
            
            full_response = ""
            async for chunk in llm_client.stream_chat(
                user_prompt,
                system=system_prompt,
                temperature=0.7,  # Lower temperature for more controlled output
                max_tokens=150,
            ):
                if chunk:
                    full_response += chunk
            
            copy_text = full_response.strip()
            
            # Validate output
            is_valid, error_msg = validate_copy_output(copy_text, max_length)
            if is_valid:
                llm_used = True
                logger.info(
                    f"[COPY_SERVICE] ✓ LLM generation successful: "
                    f"{len(copy_text)} chars, strategy={strategy_used}"
                )
            else:
                logger.warning(
                    f"[COPY_SERVICE] ⚠ LLM output validation failed: {error_msg}, "
                    f"falling back to template"
                )
                copy_text = None
        else:
            logger.warning(f"[COPY_SERVICE] LLM not configured, using fallback")
            
    except LLMClientError as e:
        logger.warning(f"[COPY_SERVICE] ⚠ LLM error: {e}, falling back to template")
    except Exception as e:
        logger.error(
            f"[COPY_SERVICE] ✗ Unexpected error during LLM generation: {e}",
            exc_info=True,
        )
    
    # Step 3: Fallback to rule-based template
    if not copy_text or not llm_used:
        logger.info(f"[COPY_SERVICE] Step 3: Using fallback template...")
        copy_text = generate_fallback_copy(
            product=product,
            intent_level=intent_level,
            max_length=max_length,
        )
        llm_used = False
        logger.info(
            f"[COPY_SERVICE] ✓ Fallback copy generated: {len(copy_text)} chars"
        )
    
    # Log AI task
    try:
        task_id = str(uuid.uuid4())
        await log_ai_task(
            db=db,
            task_type="generate_copy",
            input_data={"sku": sku, "intent_level": intent_level},
            output_data={"copy": copy_text, "llm_used": llm_used},
            task_id=task_id,
        )
    except Exception as e:
        logger.warning(f"[COPY_SERVICE] Failed to log AI task: {e}")
    
    logger.info(f"[COPY_SERVICE] ========== Generation Completed ==========")
    
    return copy_text, llm_used, strategy_used


def _get_strategy_description(intent_level: str) -> str:
    """Get strategy description for logging."""
    strategies = {
        "high": "主动推进（询问尺码/提醒库存）",
        "hesitating": "消除顾虑（轻量提问）",
        "medium": "场景化推荐",
        "low": "轻量提醒（不施压）",
    }
    return strategies.get(intent_level, "场景化推荐")


# Legacy function for backward compatibility
def prepare_copy_generation(
    db: Session,
    sku: str,
    style: CopyStyle = CopyStyle.natural,
) -> tuple[Product, str, int, bool, list[str], str]:
    """
    Legacy function for backward compatibility.
    
    This function is kept for existing code that uses the old API.
    New code should use generate_private_chat_copy().
    """
    logger.warning(
        "[COPY_SERVICE] Using legacy prepare_copy_generation(), "
        "consider migrating to generate_private_chat_copy()"
    )
    
    # Load product
    product = get_product_by_sku(db, sku)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product with SKU {sku} not found")
    
    # Retrieve RAG context (legacy behavior)
    rag_service = get_rag_service()
    rag_context = []
    rag_used = False
    
    if rag_service.is_available():
        query_parts = [product.name]
        if product.tags:
            query_parts.extend(product.tags[:3])
        query = " ".join(query_parts)
        
        rag_context, diagnostics = rag_service.retrieve_context(
            query, top_k=3, current_sku=sku
        )
        rag_used = len(rag_context) > 0
    
    # Build legacy prompt (using old PromptBuilder)
    from app.services.prompt_builder import PromptBuilder
    
    prompt_builder = PromptBuilder()
    prompt = prompt_builder.build_copy_prompt(product, style, rag_context if rag_used else None)
    prompt_tokens = prompt_builder.estimate_tokens(prompt)
    
    llm_client = get_llm_client()
    model_name = (
        llm_client.settings.llm_model
        if (llm_client.settings.llm_api_key and llm_client.settings.llm_base_url)
        else "template-fallback"
    )
    
    return product, prompt, prompt_tokens, rag_used, rag_context, model_name

"""Copy tool for generating marketing copy."""
from __future__ import annotations

import logging
from typing import Any

from app.agents.context import AgentContext
from app.schemas.copy_schemas import CopyStyle
from app.services.llm_client import LLMClientError, get_llm_client
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


async def generate_marketing_copy(
    context: AgentContext,
    style: CopyStyle = CopyStyle.natural,
    **kwargs: Any,
) -> AgentContext:
    """
    Generate marketing copy using LLM and add it to context messages.
    
    This tool uses prompt_builder to construct a prompt, calls llm_client.stream_chat
    to generate copy, and updates context.messages with the generated text.
    
    Args:
        context: Agent context (should have product and optionally rag_chunks set)
        style: Copy style (natural, professional, funny) - default: natural
        **kwargs: Additional arguments (ignored)
    
    Returns:
        Updated AgentContext with generated copy added to messages
    
    Example:
        >>> context = AgentContext(sku="8WZ01CM1")
        >>> context.product = Product(name="舒适跑鞋", ...)
        >>> context.rag_chunks = ["相关商品信息..."]
        >>> context = await generate_marketing_copy(context, style=CopyStyle.natural)
        >>> print(context.messages[-1]["content"])
        '这是一款舒适的跑鞋...'
    """
    logger.info("=" * 80)
    logger.info("[COPY_TOOL] Generating marketing copy")
    logger.info(
        f"[COPY_TOOL] Context: sku={context.sku}, "
        f"style={style.value}, has_product={context.product is not None}, "
        f"rag_chunks={len(context.rag_chunks)}"
    )
    
    if not context.product:
        error_msg = "Product is required in context to generate copy"
        logger.error(f"[COPY_TOOL] ✗ {error_msg}")
        context.add_message(
            "assistant",
            "抱歉，无法生成文案：缺少商品信息。",
        )
        return context
    
    try:
        # Build prompt using PromptBuilder
        prompt_builder = PromptBuilder()
        prompt = prompt_builder.build_copy_prompt(
            product=context.product,
            style=style,
            rag_context=context.rag_chunks if context.rag_chunks else None,
        )
        
        logger.info(f"[COPY_TOOL] Prompt built: {len(prompt)} chars")
        
        # Get LLM client
        llm_client = get_llm_client()
        system_prompt = "你是一个专业的鞋类销售文案写手，擅长写吸引人的朋友圈文案。"
        
        # Generate copy using streaming LLM
        logger.info("[COPY_TOOL] Calling LLM to generate copy...")
        full_response = ""
        
        try:
            async for chunk in llm_client.stream_chat(
                prompt,
                system=system_prompt,
                temperature=0.8,
                max_tokens=200,
            ):
                if chunk:
                    full_response += chunk
        except LLMClientError as e:
            logger.error(f"[COPY_TOOL] ✗ LLM streaming failed: {e}")
            # Fallback message
            full_response = "抱歉，文案生成失败，请稍后重试。"
        
        # Clean up response
        full_response = full_response.strip()
        
        if not full_response:
            full_response = "抱歉，未能生成文案内容。"
        
        # Add generated copy to context messages
        context.add_message("assistant", full_response)
        
        logger.info(
            f"[COPY_TOOL] ✓ Copy generated: {len(full_response)} chars, "
            f"style={style.value}"
        )
        logger.info(f"[COPY_TOOL] Generated copy: {full_response[:100]}...")
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(
            f"[COPY_TOOL] ✗ Error generating marketing copy: {e}",
            exc_info=True,
        )
        # Add error message to context
        context.add_message(
            "assistant",
            "抱歉，文案生成过程中出现错误，请稍后重试。",
        )
        return context


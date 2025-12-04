"""RAG tool for retrieving relevant context from vector store."""
from __future__ import annotations

import logging
from typing import Any, List

from app.agents.context import AgentContext
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


async def retrieve_rag(
    context: AgentContext,
    top_k: int = 3,
    **kwargs: Any,
) -> AgentContext:
    """
    检索 RAG 上下文并添加到上下文。
    
    调用逻辑：
    - 通常在 classify_intent 和 anti_disturb_check 之后执行（retrieve_rag）
    - 前提条件：context.product 应已设置（用于构建查询）
    - 调用场景：规划器根据意图级别决定是否调用（低意图会跳过）
    - 调用后：context.rag_chunks 被填充，供 generate_copy 使用以增强文案质量
    - 条件判断：如果意图为 low，规划器会跳过此步骤以节省资源
    
    This tool calls rag_service.retrieve_context() to get relevant chunks
    based on product information, and saves them into context.rag_chunks.
    
    Args:
        context: Agent context (should have product set for better retrieval)
        top_k: Number of top results to retrieve (default: 3)
        **kwargs: Additional arguments (ignored)
    
    Returns:
        Updated AgentContext with rag_chunks populated
    
    Example:
        >>> context = AgentContext(sku="8WZ01CM1")
        >>> context.product = Product(name="舒适跑鞋", ...)
        >>> context = await retrieve_rag(context, top_k=3)
        >>> print(len(context.rag_chunks))
        3
    """
    logger.info("=" * 80)
    logger.info("[RAG_TOOL] Retrieving RAG context")
    logger.info(f"[RAG_TOOL] Context: sku={context.sku}, top_k={top_k}")
    
    try:
        # Get RAG service
        rag_service = get_rag_service()
        
        if not rag_service.is_available():
            logger.warning(
                "[RAG_TOOL] RAG service not available, returning empty chunks"
            )
            context.rag_chunks = []
            return context
        
        # Build query from product information
        query_parts = []
        
        if context.product:
            query_parts.append(context.product.name)
            if context.product.tags:
                if isinstance(context.product.tags, list):
                    query_parts.extend(context.product.tags[:3])
                else:
                    query_parts.append(str(context.product.tags))
        elif context.sku:
            query_parts.append(context.sku)
        else:
            logger.warning(
                "[RAG_TOOL] No product or SKU in context, using default query"
            )
            query_parts.append("商品")
        
        query = " ".join(query_parts)
        
        logger.info(f"[RAG_TOOL] Query: '{query}'")
        
        # Retrieve context
        chunks = rag_service.retrieve_context(query, top_k=top_k)
        
        # Update context
        context.rag_chunks = chunks
        
        logger.info(
            f"[RAG_TOOL] ✓ Retrieved {len(chunks)} RAG chunks "
            f"for query: '{query[:50]}...'"
        )
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(f"[RAG_TOOL] ✗ Error retrieving RAG context: {e}", exc_info=True)
        # Return empty chunks on error
        context.rag_chunks = []
        return context


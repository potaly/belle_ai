"""RAG tool for retrieving relevant context from vector store with strict SKU validation."""
from __future__ import annotations

import logging
from typing import Any

from app.agents.context import AgentContext
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)


async def retrieve_rag(
    context: AgentContext,
    top_k: int = 3,
    **kwargs: Any,
) -> AgentContext:
    """
    检索 RAG 上下文并添加到上下文（严格 SKU 验证）。
    
    调用逻辑：
    - 通常在 classify_intent 和 anti_disturb_check 之后执行（retrieve_rag）
    - 前提条件：context.product 应已设置（用于构建查询和 SKU 验证）
    - 调用场景：规划器根据意图级别决定是否调用（低意图会跳过）
    - 调用后：context.rag_chunks 被填充，context.extra["rag_diagnostics"] 保存诊断信息
    - 安全保证：所有包含其他 SKU 的 chunks 都会被过滤，防止串货
    
    核心业务规则：
    1. 当前 SKU 是唯一的事实来源
    2. RAG 内容仅用于表达方式或背景知识
    3. 任何包含其他 SKU 的 chunk 必须被过滤
    4. 如果没有安全的 chunks，rag_used=false（优雅降级）
    
    Args:
        context: Agent context (should have product and sku set for validation)
        top_k: Number of top results to retrieve (default: 3)
        **kwargs: Additional arguments (ignored)
    
    Returns:
        Updated AgentContext with rag_chunks and rag_diagnostics populated
    
    Example:
        >>> context = AgentContext(sku="8WZ01CM1")
        >>> context.product = Product(name="舒适跑鞋", sku="8WZ01CM1", ...)
        >>> context = await retrieve_rag(context, top_k=3)
        >>> print(len(context.rag_chunks))
        3
        >>> print(context.extra["rag_diagnostics"]["safe_count"])
        3
    """
    logger.info("=" * 80)
    logger.info("[RAG_TOOL] Retrieving RAG context with strict SKU validation")
    logger.info(f"[RAG_TOOL] Context: sku={context.sku}, top_k={top_k}")
    
    try:
        # Get RAG service
        rag_service = get_rag_service()
        
        if not rag_service.is_available():
            logger.warning(
                "[RAG_TOOL] RAG service not available, returning empty chunks"
            )
            context.rag_chunks = []
            context.extra["rag_diagnostics"] = {
                "retrieved_count": 0,
                "filtered_count": 0,
                "safe_count": 0,
                "filter_reasons": [],
            }
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
        
        # Retrieve context with strict SKU validation
        current_sku = context.sku
        safe_chunks, diagnostics = rag_service.retrieve_context(
            query, top_k=top_k, current_sku=current_sku
        )
        
        # Update context
        context.rag_chunks = safe_chunks
        context.extra["rag_diagnostics"] = diagnostics.to_dict()
        
        # Log diagnostics
        logger.info(
            f"[RAG_TOOL] ✓ RAG retrieval completed: "
            f"retrieved={diagnostics.retrieved_count}, "
            f"filtered={diagnostics.filtered_count}, "
            f"safe={diagnostics.safe_count}"
        )
        
        if diagnostics.filtered_count > 0:
            logger.info(
                f"[RAG_TOOL] Filter reasons: {diagnostics.filter_reasons[:3]}"
            )
        
        # 如果没有安全的 chunks，记录警告
        if not safe_chunks and diagnostics.retrieved_count > 0:
            logger.warning(
                "[RAG_TOOL] ⚠ No safe chunks after filtering. "
                "RAG will not be used (rag_used=false)."
            )
        
        logger.info("=" * 80)
        
        return context
        
    except Exception as e:
        logger.error(f"[RAG_TOOL] ✗ Error retrieving RAG context: {e}", exc_info=True)
        # Return empty chunks on error
        context.rag_chunks = []
        context.extra["rag_diagnostics"] = {
            "retrieved_count": 0,
            "filtered_count": 0,
            "safe_count": 0,
            "filter_reasons": [f"Error: {str(e)}"],
        }
        return context

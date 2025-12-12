"""RAG service for retrieving relevant context with strict SKU ownership validation.

重构说明：
- 严格过滤包含其他 SKU 的 chunks，防止串货、价格错误、材质错误
- 当前 SKU 是唯一的事实来源
- RAG 内容仅用于表达方式或背景知识
- 如果没有安全的 chunks，系统必须优雅降级
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


@dataclass
class RAGDiagnostics:
    """
    RAG 检索诊断信息（用于可观测性和调试）。
    
    记录检索和过滤的详细信息，帮助理解为什么某些 chunks 被过滤。
    """
    retrieved_count: int = 0  # 检索到的 chunks 总数
    filtered_count: int = 0  # 被过滤的 chunks 数量
    safe_count: int = 0  # 安全的 chunks 数量（最终使用）
    filter_reasons: List[str] = None  # 过滤原因列表
    
    def __post_init__(self) -> None:
        """初始化 filter_reasons。"""
        if self.filter_reasons is None:
            self.filter_reasons = []
    
    def to_dict(self) -> dict:
        """转换为字典格式（用于 API 响应）。"""
        return {
            "retrieved_count": self.retrieved_count,
            "filtered_count": self.filtered_count,
            "safe_count": self.safe_count,
            "filter_reasons": self.filter_reasons,
        }


def get_rag_service() -> "RAGService":
    """Get or create the global RAG service instance."""
    return RAGService()


class RAGService:
    """Service for RAG (Retrieval Augmented Generation) context retrieval with strict SKU validation."""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Initialize RAG service.
        
        Args:
            vector_store: Vector store instance (optional, will create if not provided)
        """
        if vector_store is None:
            # Create a new instance (will be loaded lazily)
            vector_store = VectorStore()
            vector_store.load()  # Try to load existing index
        self.vector_store = vector_store

    def retrieve_context(
        self,
        query: str,
        top_k: int = 3,
        current_sku: Optional[str] = None,
    ) -> tuple[List[str], RAGDiagnostics]:
        """
        检索相关上下文，并严格验证 SKU 所有权。
        
        核心业务规则：
        1. 当前 SKU 是唯一的事实来源
        2. RAG 内容仅用于表达方式或背景知识
        3. 任何包含其他 SKU 的 chunk 必须被过滤
        4. 如果没有安全的 chunks，返回空列表（优雅降级）
        
        Args:
            query: Query text for retrieval
            top_k: Number of top results to return
            current_sku: Current product SKU (for filtering foreign SKUs)
        
        Returns:
            Tuple of (safe_chunks, diagnostics):
            - safe_chunks: List of safe text chunks (no foreign SKUs)
            - diagnostics: RAGDiagnostics with filtering details
        """
        diagnostics = RAGDiagnostics()
        
        if not self.vector_store.is_loaded():
            logger.warning(
                "[RAG] Vector store not loaded, returning empty context. "
                "Run python app/db/init_vector_store.py to initialize."
            )
            return [], diagnostics
        
        logger.info(f"[RAG] Retrieving context for query: '{query[:50]}...' (top_k={top_k})")
        
        try:
            # Search for similar chunks (retrieve more to account for filtering)
            retrieve_count = top_k * 3 if current_sku else top_k
            results = self.vector_store.search(query, top_k=retrieve_count)
            
            # Extract chunk texts
            all_chunks = [chunk for chunk, score in results]
            diagnostics.retrieved_count = len(all_chunks)
            
            logger.info(
                f"[RAG] Retrieved {len(all_chunks)} chunks "
                f"(min_score={min([s for _, s in results]) if results else 0:.4f})"
            )
            
            # Filter chunks by SKU ownership (strict validation)
            if current_sku:
                safe_chunks, filter_reasons = self._filter_by_sku_ownership(
                    all_chunks, current_sku
                )
                diagnostics.filtered_count = len(all_chunks) - len(safe_chunks)
                diagnostics.safe_count = len(safe_chunks)
                diagnostics.filter_reasons = filter_reasons
                
                logger.info(
                    f"[RAG] After SKU filtering: {len(safe_chunks)} safe chunks "
                    f"(filtered {diagnostics.filtered_count} chunks)"
                )
                
                # Take only top_k safe chunks
                safe_chunks = safe_chunks[:top_k]
            else:
                # No SKU provided: use all chunks (but log warning)
                logger.warning(
                    "[RAG] No current_sku provided, cannot validate SKU ownership. "
                    "Using all retrieved chunks (may contain foreign SKUs)."
                )
                safe_chunks = all_chunks[:top_k]
                diagnostics.safe_count = len(safe_chunks)
            
            # 如果没有安全的 chunks，优雅降级
            if not safe_chunks and diagnostics.retrieved_count > 0:
                logger.warning(
                    f"[RAG] ⚠ All {diagnostics.retrieved_count} retrieved chunks were filtered. "
                    f"RAG will not be used (rag_used=false)."
                )
            
            logger.info(
                f"[RAG] ✓ Returning {len(safe_chunks)} safe chunks "
                f"(retrieved={diagnostics.retrieved_count}, "
                f"filtered={diagnostics.filtered_count}, "
                f"safe={diagnostics.safe_count})"
            )
            
            return safe_chunks, diagnostics
            
        except Exception as e:
            logger.error(f"[RAG] ✗ Error retrieving context: {e}", exc_info=True)
            return [], diagnostics

    def _filter_by_sku_ownership(
        self,
        chunks: List[str],
        current_sku: str,
    ) -> tuple[List[str], List[str]]:
        """
        根据 SKU 所有权过滤 chunks（严格验证）。
        
        业务规则：
        - 只保留不包含任何 SKU 标记的 chunks（通用知识）
        - 或者只保留明确标记为当前 SKU 的 chunks（但通常我们过滤掉当前 SKU，避免重复）
        - 过滤掉包含其他 SKU 的 chunks（防止串货）
        
        Args:
            chunks: List of text chunks to filter
            current_sku: Current product SKU
        
        Returns:
            Tuple of (safe_chunks, filter_reasons):
            - safe_chunks: List of safe chunks (no foreign SKUs)
            - filter_reasons: List of reasons why chunks were filtered
        """
        safe_chunks: List[str] = []
        filter_reasons: List[str] = []
        
        # Pattern to match SKU markers: [SKU:xxx] or SKU:xxx
        sku_pattern = re.compile(r'\[SKU:([^\]]+)\]|SKU:\s*([A-Z0-9]+)', re.IGNORECASE)
        
        for chunk in chunks:
            # Find all SKU references in chunk
            sku_matches = sku_pattern.findall(chunk)
            found_skus = []
            
            for match in sku_matches:
                # match is tuple: (from [SKU:xxx], from SKU:xxx)
                sku = match[0] or match[1]
                if sku:
                    found_skus.append(sku.upper())
            
            # Decision logic:
            # 1. If chunk contains current SKU → filter out (avoid redundancy)
            # 2. If chunk contains other SKU → filter out (prevent cross-SKU contamination)
            # 3. If chunk contains no SKU → safe (generic knowledge)
            
            if current_sku.upper() in found_skus:
                # Chunk contains current SKU → filter out (we already have product data)
                filter_reasons.append(
                    f"Chunk contains current SKU {current_sku} (redundant with product data)"
                )
                logger.debug(
                    f"[RAG] Filtered chunk (current SKU): {chunk[:50]}..."
                )
                continue
            
            if found_skus:
                # Chunk contains other SKU(s) → filter out (prevent cross-SKU contamination)
                foreign_skus = [sku for sku in found_skus if sku != current_sku.upper()]
                if foreign_skus:
                    filter_reasons.append(
                        f"Chunk contains foreign SKU(s): {', '.join(foreign_skus)} "
                        f"(prevent cross-SKU contamination)"
                    )
                    logger.debug(
                        f"[RAG] Filtered chunk (foreign SKU {foreign_skus}): {chunk[:50]}..."
                    )
                    continue
            
            # Chunk is safe (no SKU or only generic knowledge)
            safe_chunks.append(chunk)
        
        return safe_chunks, filter_reasons

    def is_available(self) -> bool:
        """Check if RAG service is available (vector store loaded)."""
        return self.vector_store.is_loaded()

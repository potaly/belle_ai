"""RAG service for retrieving relevant context."""
from __future__ import annotations

import logging
from typing import List, Optional

from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


def get_rag_service() -> "RAGService":
    """Get or create the global RAG service instance."""
    return RAGService()


class RAGService:
    """Service for RAG (Retrieval Augmented Generation) context retrieval."""

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
    ) -> List[str]:
        """
        Retrieve relevant context from vector store.
        
        Args:
            query: Query text for retrieval
            top_k: Number of top results to return
        
        Returns:
            List of relevant text chunks (context)
        """
        if not self.vector_store.is_loaded():
            logger.warning(
                "[RAG] Vector store not loaded, returning empty context. "
                "Run python app/db/init_vector_store.py to initialize."
            )
            return []
        
        logger.info(f"[RAG] Retrieving context for query: '{query[:50]}...' (top_k={top_k})")
        
        try:
            # Search for similar chunks
            results = self.vector_store.search(query, top_k=top_k)
            
            # Extract chunk texts
            context_chunks = [chunk for chunk, score in results]
            
            logger.info(
                f"[RAG] ✓ Retrieved {len(context_chunks)} context chunks "
                f"(min_score={min([s for _, s in results]) if results else 0:.4f})"
            )
            
            return context_chunks
            
        except Exception as e:
            logger.error(f"[RAG] ✗ Error retrieving context: {e}", exc_info=True)
            return []

    def is_available(self) -> bool:
        """Check if RAG service is available (vector store loaded)."""
        return self.vector_store.is_loaded()


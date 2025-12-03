"""FAISS vector store for RAG."""
from __future__ import annotations

import asyncio
import logging
import pickle
from pathlib import Path
from typing import List, Tuple

import faiss
import numpy as np

from app.services.embedding_client import get_embedding_client

logger = logging.getLogger(__name__)


def _run_async(coro):
    """
    Run async coroutine, handling both cases:
    - If event loop is running, run in a separate thread with new event loop
    - If no event loop, use asyncio.run()
    """
    try:
        # Check if there's a running event loop
        asyncio.get_running_loop()
        # Event loop is already running, need to run in a separate thread
        import concurrent.futures
        
        def run_in_thread():
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()
    except RuntimeError:
        # No event loop running, can use asyncio.run()
        return asyncio.run(coro)


class VectorStore:
    """
    FAISS-based vector store for semantic search.
    
    Uses L2 (Euclidean) distance for similarity search.
    All vectors are normalized before indexing for better performance.
    """

    def __init__(self, index_path: str = "./vector_store/faiss.index", chunk_metadata_path: str = "./vector_store/chunks.pkl"):
        """
        Initialize vector store.
        
        Args:
            index_path: Path to save/load FAISS index
            chunk_metadata_path: Path to save/load chunk texts
        """
        self.index_path = Path(index_path)
        self.chunk_metadata_path = Path(chunk_metadata_path)
        self.index: faiss.Index | None = None
        self.chunks: List[str] = []
        self.dimension: int = 1536  # Default OpenAI ada-002 dimension
        
        # Create directory if it doesn't exist
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.chunk_metadata_path.parent.mkdir(parents=True, exist_ok=True)

    def build_index(self, chunks: List[str]) -> None:
        """
        Build FAISS index from text chunks.
        
        Args:
            chunks: List of text chunks to index
        """
        if not chunks:
            logger.warning("No chunks provided, skipping index build")
            return
        
        logger.info(f"[VECTOR_STORE] Building index for {len(chunks)} chunks...")
        
        # Get embeddings
        embedding_client = get_embedding_client()
        
        # Generate embeddings (handle both sync and async contexts)
        embeddings = _run_async(embedding_client.embed_texts(chunks))
        
        if not embeddings:
            raise ValueError("Failed to generate embeddings")
        
        # Determine dimension from first embedding
        self.dimension = len(embeddings[0])
        logger.info(f"[VECTOR_STORE] Embedding dimension: {self.dimension}")
        
        # Convert to numpy array
        embeddings_array = np.array(embeddings, dtype=np.float32)
        
        # 验证归一化前的向量模长（调试用）
        sample_norm_before = np.linalg.norm(embeddings_array[0])
        logger.info(
            f"[VECTOR_STORE] Sample vector norm before normalization: {sample_norm_before:.4f} "
            f"(should be > 0, typically 10-50 for raw embeddings)"
        )
        
        # 强制归一化向量（L2 normalization）
        # 这确保所有向量都在单位球面上，L2距离才能正确代表余弦相似度
        faiss.normalize_L2(embeddings_array)
        
        # 验证归一化后的向量模长（应该是1.0）
        sample_norm_after = np.linalg.norm(embeddings_array[0])
        if abs(sample_norm_after - 1.0) > 0.01:
            logger.warning(
                f"[VECTOR_STORE] ⚠️ Vector normalization may have failed! "
                f"Expected norm=1.0, got {sample_norm_after:.4f}"
            )
        else:
            logger.info(
                f"[VECTOR_STORE] ✓ Vectors normalized (L2), sample norm={sample_norm_after:.4f} "
                f"(should be 1.0)"
            )
        
        # Create FAISS index
        # Using IndexFlatL2 for exact search (can be upgraded to IndexIVFFlat for large datasets)
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Add vectors to index
        self.index.add(embeddings_array)
        self.chunks = chunks
        
        logger.info(
            f"[VECTOR_STORE] ✓ Index built: {self.index.ntotal} vectors, "
            f"dim={self.dimension}"
        )

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Search for similar chunks.
        
        Args:
            query: Query text
            top_k: Number of results to return
        
        Returns:
            List of (chunk_text, similarity_score) tuples
            Lower score means more similar (L2 distance)
        """
        if self.index is None or len(self.chunks) == 0:
            logger.warning("Index not loaded, returning empty results")
            return []
        
        if not query or not query.strip():
            return []
        
        logger.info(f"[VECTOR_STORE] Searching for: '{query[:50]}...' (top_k={top_k})")
        
        # Get query embedding
        embedding_client = get_embedding_client()
        query_embeddings = _run_async(embedding_client.embed_texts([query]))
        
        if not query_embeddings:
            logger.warning("Failed to generate query embedding")
            return []
        
        query_vector = np.array([query_embeddings[0]], dtype=np.float32)
        
        # 验证归一化前的查询向量模长（调试用）
        query_norm_before = np.linalg.norm(query_vector[0])
        logger.info(
            f"[VECTOR_STORE] Query vector norm before normalization: {query_norm_before:.4f}"
        )
        
        # 强制归一化查询向量（L2 normalization）
        # 确保查询向量和索引向量在同一个单位球面上
        faiss.normalize_L2(query_vector)
        
        # 验证归一化后的查询向量模长（应该是1.0）
        query_norm_after = np.linalg.norm(query_vector[0])
        if abs(query_norm_after - 1.0) > 0.01:
            logger.warning(
                f"[VECTOR_STORE] ⚠️ Query vector normalization may have failed! "
                f"Expected norm=1.0, got {query_norm_after:.4f}"
            )
        else:
            logger.info(
                f"[VECTOR_STORE] ✓ Query vector normalized, norm={query_norm_after:.4f} "
                f"(should be 1.0)"
            )
        
        # Search
        distances, indices = self.index.search(query_vector, min(top_k, self.index.ntotal))
        
        # 调试输出：显示距离分布
        if len(distances[0]) > 0:
            min_dist = float(distances[0][0])
            max_dist = float(distances[0][-1])
            avg_dist = float(np.mean(distances[0]))
            logger.info(
                f"[VECTOR_STORE] Distance stats: min={min_dist:.4f}, "
                f"max={max_dist:.4f}, avg={avg_dist:.4f} "
                f"(for normalized vectors, should be 0-2, <1.0 for similar items)"
            )
        
        # Build results
        results: List[Tuple[str, float]] = []
        for i, (idx, dist) in enumerate(zip(indices[0], distances[0])):
            if idx < len(self.chunks):
                results.append((self.chunks[idx], float(dist)))
        
        logger.info(
            f"[VECTOR_STORE] ✓ Found {len(results)} results "
            f"(min_dist={min([r[1] for r in results]) if results else 0:.4f})"
        )
        
        return results

    def save(self) -> None:
        """Save index and chunks to disk."""
        if self.index is None:
            logger.warning("No index to save")
            return
        
        # Save FAISS index
        faiss.write_index(self.index, str(self.index_path))
        logger.info(f"[VECTOR_STORE] Saved index to {self.index_path}")
        
        # Save chunk metadata
        with open(self.chunk_metadata_path, 'wb') as f:
            pickle.dump(self.chunks, f)
        logger.info(f"[VECTOR_STORE] Saved {len(self.chunks)} chunks to {self.chunk_metadata_path}")

    def load(self) -> bool:
        """
        Load index and chunks from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.index_path.exists() or not self.chunk_metadata_path.exists():
            logger.warning(
                f"Index files not found: {self.index_path} or {self.chunk_metadata_path}"
            )
            return False
        
        try:
            # Load FAISS index
            self.index = faiss.read_index(str(self.index_path))
            self.dimension = self.index.d
            logger.info(
                f"[VECTOR_STORE] Loaded index: {self.index.ntotal} vectors, "
                f"dim={self.dimension}"
            )
            
            # Load chunk metadata
            with open(self.chunk_metadata_path, 'rb') as f:
                self.chunks = pickle.load(f)
            logger.info(f"[VECTOR_STORE] Loaded {len(self.chunks)} chunks")
            
            if len(self.chunks) != self.index.ntotal:
                logger.warning(
                    f"Mismatch: {len(self.chunks)} chunks vs {self.index.ntotal} vectors"
                )
            
            return True
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            return False

    def is_loaded(self) -> bool:
        """Check if index is loaded."""
        return self.index is not None and len(self.chunks) > 0

    def get_stats(self) -> dict:
        """Get index statistics."""
        if not self.is_loaded():
            return {"loaded": False}
        
        return {
            "loaded": True,
            "num_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "num_chunks": len(self.chunks),
        }


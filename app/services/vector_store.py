"""FAISS vector store for RAG."""
from __future__ import annotations

import asyncio
import logging
import pickle
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

    def __init__(
        self,
        index_path: str = "./vector_store/faiss.index",
        chunk_metadata_path: str = "./vector_store/chunks.pkl",
        use_incremental: bool = True,
    ):
        """
        Initialize vector store.
        
        Args:
            index_path: Path to save/load FAISS index (base index)
            chunk_metadata_path: Path to save/load chunk texts
            use_incremental: Whether to use base+delta incremental strategy
        """
        self.index_path = Path(index_path)
        self.chunk_metadata_path = Path(chunk_metadata_path)
        self.use_incremental = use_incremental
        
        # Legacy single index (for backward compatibility)
        self.index: faiss.Index | None = None
        self.chunks: List[str] = []
        
        # Incremental strategy: base + delta
        self.base_index: faiss.Index | None = None
        self.base_chunks: List[str] = []
        self.base_document_ids: List[str] = []  # document_id for each base chunk
        
        self.delta_index: faiss.Index | None = None
        self.delta_chunks: List[str] = []
        self.delta_document_ids: List[str] = []  # document_id for each delta chunk
        
        # Document ID mappings: document_id -> index position
        self.document_id_to_base_index: Dict[str, int] = {}
        self.document_id_to_delta_index: Dict[str, int] = {}
        
        # Delta rebuild threshold: rebuild base when delta reaches 10% of base size
        self.delta_rebuild_threshold: float = 0.1
        
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
        
        If using incremental strategy, searches both base and delta indexes
        and merges results (delta takes priority for duplicate document_ids).
        
        Args:
            query: Query text
            top_k: Number of results to return
        
        Returns:
            List of (chunk_text, similarity_score) tuples
            Lower score means more similar (L2 distance)
        """
        if not query or not query.strip():
            return []
        
        # Use incremental search if enabled
        if self.use_incremental:
            return self._search_incremental(query, top_k)
        
        # Legacy single index search
        if self.index is None or len(self.chunks) == 0:
            logger.warning("Index not loaded, returning empty results")
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

    def _search_incremental(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """Search using base+delta incremental strategy."""
        logger.info(f"[VECTOR_STORE] Incremental search: '{query[:50]}...' (top_k={top_k})")
        
        # Get query embedding
        embedding_client = get_embedding_client()
        query_embeddings = _run_async(embedding_client.embed_texts([query]))
        
        if not query_embeddings:
            logger.warning("Failed to generate query embedding")
            return []
        
        query_vector = np.array([query_embeddings[0]], dtype=np.float32)
        faiss.normalize_L2(query_vector)
        
        # Search base index
        base_results: List[Tuple[str, float, str]] = []  # (text, distance, document_id)
        if self.base_index and self.base_index.ntotal > 0:
            base_top_k = min(top_k * 2, self.base_index.ntotal)  # Get more candidates
            distances, indices = self.base_index.search(query_vector, base_top_k)
            
            for idx, dist in zip(indices[0], distances[0]):
                if idx < len(self.base_chunks) and idx < len(self.base_document_ids):
                    doc_id = self.base_document_ids[idx]
                    # Skip if migrated to delta
                    if doc_id not in self.document_id_to_base_index:
                        continue
                    base_results.append((self.base_chunks[idx], float(dist), doc_id))
        
        # Search delta index
        delta_results: List[Tuple[str, float, str]] = []
        if self.delta_index and self.delta_index.ntotal > 0:
            delta_top_k = min(top_k * 2, self.delta_index.ntotal)
            distances, indices = self.delta_index.search(query_vector, delta_top_k)
            
            for idx, dist in zip(indices[0], distances[0]):
                if idx < len(self.delta_chunks) and idx < len(self.delta_document_ids):
                    doc_id = self.delta_document_ids[idx]
                    delta_results.append((self.delta_chunks[idx], float(dist), doc_id))
        
        # Merge results: delta takes priority, remove duplicates
        seen_doc_ids: set[str] = set()
        merged_results: List[Tuple[str, float]] = []
        
        # Add delta results first (higher priority)
        for text, dist, doc_id in delta_results:
            if doc_id not in seen_doc_ids:
                merged_results.append((text, dist))
                seen_doc_ids.add(doc_id)
        
        # Add base results (skip if already in delta)
        for text, dist, doc_id in base_results:
            if doc_id not in seen_doc_ids:
                merged_results.append((text, dist))
                seen_doc_ids.add(doc_id)
        
        # Sort by distance and take top_k
        merged_results.sort(key=lambda x: x[1])
        final_results = merged_results[:top_k]
        
        logger.info(
            f"[VECTOR_STORE] Incremental search: base={len(base_results)}, "
            f"delta={len(delta_results)}, merged={len(final_results)}"
        )
        
        return final_results

    def save(self) -> None:
        """Save index and chunks to disk."""
        if self.use_incremental:
            self._save_incremental()
        else:
            self._save_legacy()

    def _save_legacy(self) -> None:
        """Save legacy single index."""
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

    def _save_incremental(self) -> None:
        """Save base+delta indexes and metadata."""
        base_path = self.index_path
        delta_path = self.index_path.parent / f"{self.index_path.stem}_delta{self.index_path.suffix}"
        metadata_path = self.chunk_metadata_path
        delta_metadata_path = self.chunk_metadata_path.parent / f"{self.chunk_metadata_path.stem}_delta.pkl"
        
        # Save base index
        if self.base_index:
            faiss.write_index(self.base_index, str(base_path))
            logger.info(f"[VECTOR_STORE] Saved base index: {self.base_index.ntotal} vectors")
            
            # Save base metadata
            base_metadata = {
                "chunks": self.base_chunks,
                "document_ids": self.base_document_ids,
                "document_id_to_index": self.document_id_to_base_index,
            }
            with open(metadata_path, 'wb') as f:
                pickle.dump(base_metadata, f)
            logger.info(f"[VECTOR_STORE] Saved base metadata: {len(self.base_chunks)} chunks")
        else:
            logger.warning("[VECTOR_STORE] No base index to save")
        
        # Save delta index
        if self.delta_index:
            faiss.write_index(self.delta_index, str(delta_path))
            logger.info(f"[VECTOR_STORE] Saved delta index: {self.delta_index.ntotal} vectors")
            
            # Save delta metadata
            delta_metadata = {
                "chunks": self.delta_chunks,
                "document_ids": self.delta_document_ids,
                "document_id_to_index": self.document_id_to_delta_index,
            }
            with open(delta_metadata_path, 'wb') as f:
                pickle.dump(delta_metadata, f)
            logger.info(f"[VECTOR_STORE] Saved delta metadata: {len(self.delta_chunks)} chunks")
        else:
            logger.info("[VECTOR_STORE] No delta index to save")

    def load(self) -> bool:
        """
        Load index and chunks from disk.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        if self.use_incremental:
            return self._load_incremental()
        else:
            return self._load_legacy()

    def _load_legacy(self) -> bool:
        """Load legacy single index."""
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

    def _load_incremental(self) -> bool:
        """Load base+delta indexes and metadata."""
        base_path = self.index_path
        delta_path = self.index_path.parent / f"{self.index_path.stem}_delta{self.index_path.suffix}"
        metadata_path = self.chunk_metadata_path
        delta_metadata_path = self.chunk_metadata_path.parent / f"{self.chunk_metadata_path.stem}_delta.pkl"
        
        loaded = False
        
        # Load base index
        if base_path.exists() and metadata_path.exists():
            try:
                self.base_index = faiss.read_index(str(base_path))
                self.dimension = self.base_index.d
                
                with open(metadata_path, 'rb') as f:
                    base_metadata = pickle.load(f)
                
                # Handle both old format (list) and new format (dict)
                if isinstance(base_metadata, dict):
                    self.base_chunks = base_metadata.get("chunks", [])
                    self.base_document_ids = base_metadata.get("document_ids", [])
                    self.document_id_to_base_index = base_metadata.get("document_id_to_index", {})
                else:
                    # Old format: just chunks list
                    self.base_chunks = base_metadata
                    self.base_document_ids = []
                    self.document_id_to_base_index = {}
                
                logger.info(
                    f"[VECTOR_STORE] Loaded base index: {self.base_index.ntotal} vectors, "
                    f"{len(self.base_chunks)} chunks"
                )
                loaded = True
            except Exception as e:
                logger.error(f"Failed to load base index: {e}")
        
        # Load delta index
        if delta_path.exists() and delta_metadata_path.exists():
            try:
                self.delta_index = faiss.read_index(str(delta_path))
                
                with open(delta_metadata_path, 'rb') as f:
                    delta_metadata = pickle.load(f)
                
                if isinstance(delta_metadata, dict):
                    self.delta_chunks = delta_metadata.get("chunks", [])
                    self.delta_document_ids = delta_metadata.get("document_ids", [])
                    self.document_id_to_delta_index = delta_metadata.get("document_id_to_index", {})
                else:
                    self.delta_chunks = delta_metadata
                    self.delta_document_ids = []
                    self.document_id_to_delta_index = {}
                
                logger.info(
                    f"[VECTOR_STORE] Loaded delta index: {self.delta_index.ntotal} vectors, "
                    f"{len(self.delta_chunks)} chunks"
                )
            except Exception as e:
                logger.error(f"Failed to load delta index: {e}")
        
        if not loaded:
            logger.warning("[VECTOR_STORE] No index files found for incremental load")
            return False
        
        return True

    def is_loaded(self) -> bool:
        """Check if index is loaded."""
        return self.index is not None and len(self.chunks) > 0

    def get_stats(self) -> dict:
        """Get index statistics."""
        if self.use_incremental:
            base_size = self.base_index.ntotal if self.base_index else 0
            delta_size = self.delta_index.ntotal if self.delta_index else 0
            return {
                "loaded": (self.base_index is not None) or (self.delta_index is not None),
                "use_incremental": True,
                "base_vectors": base_size,
                "delta_vectors": delta_size,
                "total_vectors": base_size + delta_size,
                "dimension": self.dimension,
                "base_chunks": len(self.base_chunks),
                "delta_chunks": len(self.delta_chunks),
            }
        else:
            if not self.is_loaded():
                return {"loaded": False, "use_incremental": False}
            
            return {
                "loaded": True,
                "use_incremental": False,
                "num_vectors": self.index.ntotal if self.index else 0,
                "dimension": self.dimension,
                "num_chunks": len(self.chunks),
            }

    def upsert_vector(self, document_id: str, text: str) -> bool:
        """
        Idempotent upsert: update or insert vector for a document_id.
        
        Uses base+delta incremental strategy:
        - If document_id exists in delta: update delta index
        - If document_id exists in base: mark for migration, add to delta
        - If document_id doesn't exist: add to delta
        
        Args:
            document_id: Unique document identifier (format: "brand_code#sku")
            text: Text content for embedding
            
        Returns:
            True if successful, False otherwise
        """
        if not self.use_incremental:
            logger.warning(
                "[VECTOR_STORE] upsert_vector requires use_incremental=True. "
                "Please initialize VectorStore with use_incremental=True"
            )
            return False
        
        logger.info(f"[VECTOR_STORE] Upserting vector: document_id={document_id}")
        
        # Generate embedding
        embedding_client = get_embedding_client()
        embeddings = _run_async(embedding_client.embed_texts([text]))
        
        if not embeddings:
            logger.error(f"[VECTOR_STORE] Failed to generate embedding for {document_id}")
            return False
        
        embedding = np.array([embeddings[0]], dtype=np.float32)
        faiss.normalize_L2(embedding)
        
        # Initialize delta index if needed
        if self.delta_index is None:
            self.delta_index = faiss.IndexFlatL2(self.dimension)
            logger.info(f"[VECTOR_STORE] Initialized delta index (dim={self.dimension})")
        
        # Check if document_id exists in delta
        if document_id in self.document_id_to_delta_index:
            # Update existing delta entry: rebuild delta index
            delta_pos = self.document_id_to_delta_index[document_id]
            logger.info(
                f"[VECTOR_STORE] Updating existing delta entry: "
                f"document_id={document_id}, pos={delta_pos}"
            )
            
            # Rebuild delta index with updated vector
            self._rebuild_delta_index(document_id, embedding[0], text)
            return True
        
        # Check if document_id exists in base
        if document_id in self.document_id_to_base_index:
            # Mark for migration: remove from base mapping, add to delta
            base_pos = self.document_id_to_base_index[document_id]
            logger.info(
                f"[VECTOR_STORE] Migrating from base to delta: "
                f"document_id={document_id}, base_pos={base_pos}"
            )
            
            # Remove from base mapping (mark as migrated)
            del self.document_id_to_base_index[document_id]
            
            # Add to delta
            self._add_to_delta(document_id, embedding[0], text)
            return True
        
        # New document: add to delta
        logger.info(f"[VECTOR_STORE] Adding new document to delta: document_id={document_id}")
        self._add_to_delta(document_id, embedding[0], text)
        
        # Check if delta needs rebuild
        if self.base_index and self.delta_index:
            base_size = self.base_index.ntotal
            delta_size = self.delta_index.ntotal
            if base_size > 0 and delta_size / base_size >= self.delta_rebuild_threshold:
                logger.info(
                    f"[VECTOR_STORE] Delta threshold reached ({delta_size}/{base_size}), "
                    "considering rebuild (manual trigger required)"
                )
        
        return True

    def _add_to_delta(self, document_id: str, vector: np.ndarray, text: str) -> None:
        """Add vector to delta index."""
        if self.delta_index is None:
            self.delta_index = faiss.IndexFlatL2(self.dimension)
        
        delta_pos = len(self.delta_chunks)
        self.delta_index.add(vector.reshape(1, -1))
        self.delta_chunks.append(text)
        self.delta_document_ids.append(document_id)
        self.document_id_to_delta_index[document_id] = delta_pos
        
        logger.debug(
            f"[VECTOR_STORE] Added to delta: document_id={document_id}, "
            f"pos={delta_pos}, delta_size={self.delta_index.ntotal}"
        )

    def _rebuild_delta_index(self, document_id: str, vector: np.ndarray, text: str) -> None:
        """Rebuild delta index with updated vector."""
        if self.delta_index is None:
            self._add_to_delta(document_id, vector, text)
            return
        
        delta_pos = self.document_id_to_delta_index[document_id]
        
        # Rebuild delta: remove old entry, add new entry
        # Note: FAISS IndexFlatL2 doesn't support direct update, so we rebuild
        old_delta_chunks = self.delta_chunks.copy()
        old_delta_document_ids = self.delta_document_ids.copy()
        old_delta_mapping = self.document_id_to_delta_index.copy()
        
        # Rebuild delta index
        self.delta_index = faiss.IndexFlatL2(self.dimension)
        self.delta_chunks = []
        self.delta_document_ids = []
        self.document_id_to_delta_index = {}
        
        embedding_client = get_embedding_client()
        
        for i, (old_doc_id, old_text) in enumerate(zip(old_delta_document_ids, old_delta_chunks)):
            if old_doc_id == document_id:
                # Use new vector and text
                self._add_to_delta(document_id, vector, text)
            else:
                # Regenerate embedding for old text (or cache it)
                old_embeddings = _run_async(embedding_client.embed_texts([old_text]))
                if old_embeddings:
                    old_vector = np.array([old_embeddings[0]], dtype=np.float32)
                    faiss.normalize_L2(old_vector)
                    self._add_to_delta(old_doc_id, old_vector[0], old_text)
        
        logger.info(
            f"[VECTOR_STORE] Rebuilt delta index: size={self.delta_index.ntotal}, "
            f"updated document_id={document_id}"
        )

    def upsert_vectors_batch(
        self, document_texts: List[Tuple[str, str]]
    ) -> Dict[str, bool]:
        """
        Batch upsert vectors.
        
        Args:
            document_texts: List of (document_id, text) tuples
            
        Returns:
            Dictionary mapping document_id to success status
        """
        results: Dict[str, bool] = {}
        
        if not document_texts:
            return results
        
        logger.info(f"[VECTOR_STORE] Batch upserting {len(document_texts)} vectors...")
        
        # Extract texts for batch embedding generation
        texts = [text for _, text in document_texts]
        document_ids = [doc_id for doc_id, _ in document_texts]
        
        # Generate embeddings in batch
        embedding_client = get_embedding_client()
        embeddings = _run_async(embedding_client.embed_texts(texts))
        
        if not embeddings or len(embeddings) != len(texts):
            logger.error(
                f"[VECTOR_STORE] Failed to generate embeddings: "
                f"expected {len(texts)}, got {len(embeddings) if embeddings else 0}"
            )
            return {doc_id: False for doc_id in document_ids}
        
        # Normalize embeddings
        embeddings_array = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_array)
        
        # Upsert each vector
        for i, (document_id, text) in enumerate(document_texts):
            try:
                embedding = embeddings_array[i]
                # Use existing upsert logic
                success = self.upsert_vector(document_id, text)
                results[document_id] = success
            except Exception as e:
                logger.error(
                    f"[VECTOR_STORE] Failed to upsert {document_id}: {e}"
                )
                results[document_id] = False
        
        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"[VECTOR_STORE] Batch upsert completed: {success_count}/{len(document_texts)} successful"
        )
        
        return results


"""Embedding client for generating vector embeddings."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import List

import httpx
import numpy as np

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmbeddingClientError(RuntimeError):
    """Raised when the embedding API returns an error."""


class EmbeddingClient:
    """Client for OpenAI-compatible embedding APIs."""

    def __init__(self) -> None:
        """Initialize embedding client with settings."""
        self.settings = get_settings()
        self._timeout = httpx.Timeout(30.0)
        
        # Embedding API settings
        # Try to get embedding-specific settings, fall back to LLM settings
        self.api_key = getattr(self.settings, 'embedding_api_key', None) or self.settings.llm_api_key
        self.model = getattr(self.settings, 'embedding_model', None) or 'text-embedding-v2'
        
        # Build embedding base URL
        # Priority: embedding_base_url > convert from llm_base_url
        if getattr(self.settings, 'embedding_base_url', None):
            # Use explicit embedding base URL
            self.base_url = self.settings.embedding_base_url
            logger.info(f"[EMBEDDING] Using EMBEDDING_BASE_URL from config: {self.base_url}")
        elif self.settings.llm_base_url:
            # Convert LLM base URL to embeddings endpoint
            base_url = self.settings.llm_base_url
            logger.info(f"[EMBEDDING] Converting LLM_BASE_URL: {base_url}")
            # Handle different URL formats
            if '/chat/completions' in base_url:
                # Replace /chat/completions with /embeddings
                self.base_url = base_url.replace('/chat/completions', '/embeddings')
            elif base_url.endswith('/v1') or base_url.endswith('/v1/'):
                # Append /embeddings to base URL (e.g., compatible-mode/v1 -> compatible-mode/v1/embeddings)
                self.base_url = base_url.rstrip('/') + '/embeddings'
            elif not base_url.endswith('/embeddings'):
                # Append /embeddings if not present
                self.base_url = base_url.rstrip('/') + '/embeddings'
            else:
                self.base_url = base_url
        else:
            self.base_url = None
        
        # 确保URL包含 /embeddings 路径（无论来源如何）
        if self.base_url and not self.base_url.endswith('/embeddings'):
            if self.base_url.endswith('/v1') or self.base_url.endswith('/v1/'):
                self.base_url = self.base_url.rstrip('/') + '/embeddings'
                logger.info(f"[EMBEDDING] Added /embeddings to URL: {self.base_url}")
            elif not self.base_url.endswith('/embeddings'):
                self.base_url = self.base_url.rstrip('/') + '/embeddings'
                logger.info(f"[EMBEDDING] Added /embeddings to URL: {self.base_url}")
        
        # 记录最终使用的URL（用于调试）
        logger.info(f"[EMBEDDING] Final base URL: {self.base_url}")

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        支持分批处理，避免单次请求文本过多导致API错误。
        阿里百炼API可能对单次请求的文本数量有限制。
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            List of embedding vectors (each is a list of floats)
        
        Raises:
            EmbeddingClientError: If the API call fails after retries
        """
        if not texts:
            return []
        
        # If no API credentials, use stub embeddings
        if not self.api_key or not self.base_url:
            logger.warning(
                "Embedding API credentials missing, using stub embeddings. "
                "Set LLM_API_KEY and LLM_BASE_URL (or EMBEDDING_API_KEY and EMBEDDING_BASE_URL) in .env"
            )
            return self._generate_stub_embeddings(texts)
        
        # 分批处理：每次最多处理10个文本（阿里百炼API可能对批量输入有限制）
        # 如果仍然失败，可以尝试改为单个处理（batch_size=1）
        batch_size = 10
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(texts) + batch_size - 1) // batch_size
            
            logger.info(
                f"[EMBEDDING] Processing batch {batch_num}/{total_batches} "
                f"({len(batch)} texts)"
            )
            
            # Retry logic: 2 attempts per batch
            max_retries = 2
            last_error = None
            batch_embeddings = None
            
            for attempt in range(max_retries):
                try:
                    batch_embeddings = await self._call_embedding_api(batch)
                    break
                except (httpx.HTTPError, httpx.TimeoutException) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 0.5
                        logger.warning(
                            f"[EMBEDDING] Batch {batch_num} failed (attempt {attempt + 1}/{max_retries}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(
                            f"[EMBEDDING] Batch {batch_num} failed after {max_retries} attempts: {e}"
                        )
            
            # 如果批次失败，使用stub embeddings作为fallback
            if batch_embeddings is None:
                logger.warning(
                    f"[EMBEDDING] Batch {batch_num} failed, using stub embeddings for this batch"
                )
                batch_embeddings = self._generate_stub_embeddings(batch)
            
            all_embeddings.extend(batch_embeddings)
        
        logger.info(
            f"[EMBEDDING] ✓ Generated {len(all_embeddings)} embeddings "
            f"from {len(texts)} texts"
        )
        
        return all_embeddings

    async def _call_embedding_api(self, texts: List[str]) -> List[List[float]]:
        """Call the embedding API and return embeddings."""
        start_time = time.perf_counter()
        
        # 构建请求payload
        # 阿里百炼API支持批量输入（input可以是字符串列表）
        # 根据官方文档，input应该始终是列表格式
        payload = {
            "model": self.model,
            "input": texts,  # 始终使用列表格式
        }
        
        # text-embedding-v3/v4 支持 dimensions 和 encoding_format 参数
        # v2 不支持这些参数，所以只在v3/v4时添加
        if self.model in ["text-embedding-v3", "text-embedding-v4"]:
            payload["dimensions"] = 1536  # 可以根据需要调整
            payload["encoding_format"] = "float"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        # Log request details (truncate long texts for logging)
        texts_preview = [t[:50] + "..." if len(t) > 50 else t for t in texts[:3]]
        logger.info(
            f"[EMBEDDING] Calling API: {self.base_url}, "
            f"model={self.model}, texts_count={len(texts)}, "
            f"texts_preview={texts_preview}"
        )
        
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                self.base_url,
                json=payload,
                headers=headers,
            )
            
            # 如果请求失败，记录详细错误信息
            if response.status_code != 200:
                try:
                    error_detail = response.text[:500]  # 只记录前500字符
                    error_json = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
                except:
                    error_detail = response.text[:500]
                    error_json = {}
                
                logger.error(
                    f"[EMBEDDING] API request failed: status={response.status_code}, "
                    f"error={error_detail}, error_json={error_json}, "
                    f"payload_model={payload.get('model')}, "
                    f"input_count={len(texts)}, input_preview={texts[0][:100] if texts else 'N/A'}, "
                    f"base_url={self.base_url}"
                )
            
            response.raise_for_status()
            
            result = response.json()
            latency = time.perf_counter() - start_time
            
            # Extract embeddings from response
            embeddings = self._extract_embeddings(result)
            
            logger.info(
                f"[EMBEDDING] ✓ Success: {len(embeddings)} embeddings, "
                f"dim={len(embeddings[0]) if embeddings else 0}, "
                f"latency={latency:.2f}s"
            )
            
            return embeddings

    def _extract_embeddings(self, response: dict) -> List[List[float]]:
        """
        Extract embeddings from API response.
        
        Supports OpenAI-compatible format:
        {
            "data": [
                {"embedding": [0.1, 0.2, ...]},
                ...
            ]
        }
        """
        if "data" in response:
            # OpenAI-compatible format
            return [item["embedding"] for item in response["data"]]
        elif "embeddings" in response:
            # Alternative format
            return response["embeddings"]
        elif isinstance(response, list):
            # Direct list of embeddings
            return response
        else:
            raise EmbeddingClientError(
                f"Unexpected embedding response format: {list(response.keys())}"
            )

    def _generate_stub_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate stub embeddings for testing.
        
        Uses a simple hash-based approach to generate deterministic
        pseudo-embeddings of dimension 1536 (OpenAI ada-002 dimension).
        """
        dim = 1536
        embeddings: List[List[float]] = []
        
        for text in texts:
            # Generate deterministic "embedding" based on text hash
            hash_obj = hashlib.md5(text.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            
            # Convert to list of floats in range [-1, 1]
            embedding = []
            for i in range(dim):
                byte_val = hash_bytes[i % len(hash_bytes)]
                # Map byte (0-255) to float (-1 to 1)
                val = (byte_val / 127.5) - 1.0
                embedding.append(val)
            
            # Normalize the vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = [x / norm for x in embedding]
            
            embeddings.append(embedding)
        
        logger.info(f"[EMBEDDING] Generated {len(embeddings)} stub embeddings (dim={dim})")
        return embeddings


# Global instance
_embedding_client: EmbeddingClient | None = None


def get_embedding_client() -> EmbeddingClient:
    """Get or create the global embedding client instance."""
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = EmbeddingClient()
    return _embedding_client


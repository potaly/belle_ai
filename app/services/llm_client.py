from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional
from time import perf_counter

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMClientError(RuntimeError):
    """Raised when the LLM provider returns an error."""


class LLMClient:
    """Simple client for Alibaba Bailian Qwen endpoints."""

    def __init__(self) -> None:
        self.settings = get_settings()
        # 百炼接口在高负载或网络环境一般会有一定延迟，这里放宽超时时间
        self._timeout = httpx.Timeout(30.0)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate text via Qwen HTTP endpoint."""
        if not self.settings.llm_api_key or not self.settings.llm_base_url:
            logger.warning("LLM credentials missing, falling back to local stub.")
            suffix = kwargs.get("style", "neutral")
            return f"[{self.settings.llm_model}:{suffix}] {prompt.strip()}"

        # 根据百炼 OpenAI-Compatible 接口要求，组装 chat.completions 风格请求
        messages = [
            {"role": "system", "content": kwargs.get("system", "You are a helpful sales assistant.")},
            {"role": "user", "content": prompt},
        ]
        payload: Dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
        }
        # 允许透传其他可选参数（如 temperature、max_tokens 等）
        extra: Dict[str, Any] = {k: v for k, v in kwargs.items() if k not in {"system", "style"}}
        payload.update(extra)
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

        start = perf_counter()
        # 打印关键请求参数（去除敏感信息与长文本）
        safe_payload = {
            "model": payload.get("model"),
            # 只展示用户提问前 80 字，避免日志过长和泄露隐私
            "user_message": prompt[:80],
            # 只展示部分参数
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
        }
        logger.info(
            "LLM request: url=%s, payload=%s",
            self.settings.llm_base_url,
            json.dumps(safe_payload, ensure_ascii=False),
        )

        response: httpx.Response | None = None
        max_attempts = 2
        for attempt in range(1, max_attempts + 1):
            try:
                response = httpx.post(
                    self.settings.llm_base_url,
                    headers=headers,
                    json=payload,
                    timeout=self._timeout,
                )
                logger.info(
                    "LLM response: status=%s, body_snippet=%s",
                    response.status_code,
                    response.text[:200],
                )
                response.raise_for_status()
                break
            except httpx.TimeoutException as exc:
                if attempt == max_attempts:
                    raise LLMClientError("LLM request timed out") from exc
                logger.warning(
                    "LLM request timeout on attempt %s/%s, retrying...",
                    attempt,
                    max_attempts,
                )
            except httpx.HTTPStatusError as exc:
                raise LLMClientError(f"LLM request failed: {exc}") from exc
            except httpx.RequestError as exc:
                if attempt == max_attempts:
                    raise LLMClientError(f"LLM transport error: {exc}") from exc
                logger.warning(
                    "LLM transport error on attempt %s/%s: %s. Retrying...",
                    attempt,
                    max_attempts,
                    exc,
                )
        duration_ms = (perf_counter() - start) * 1000
        logger.info("LLM request finished in %.2f ms", duration_ms)

        if response is None:
            raise LLMClientError("LLM request did not return a response")

        text = self._extract_text(response)
        if not text:
            raise LLMClientError("LLM response did not contain text output")
        return text

    @staticmethod
    def _extract_text(response: httpx.Response) -> Optional[str]:
        """Normalize provider response structure."""
        try:
            data = response.json()
        except ValueError as exc:
            raise LLMClientError("Failed to parse LLM JSON response") from exc

        # 1) OpenAI-compatible chat.completions: top-level `choices[0].message.content`
        if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
            first = data["choices"][0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
                # 兼容老式 text 字段
                if isinstance(first.get("text"), str):
                    return first["text"]

        # 2) 百炼原生 output/data 结构
        output = data.get("output") or data.get("data")
        if isinstance(output, dict):
            if "text" in output and isinstance(output["text"], str):
                return output["text"]
            if "choices" in output and isinstance(output["choices"], list):
                first = output["choices"][0]
                if isinstance(first, dict):
                    return first.get("text") or first.get("message")
        if "result" in data and isinstance(data["result"], str):
            return data["result"]
        if "data" in data and isinstance(data["data"], str):
            return data["data"]
        return None

    async def stream_chat(
        self,
        prompt: str,
        system: str = "You are a helpful sales assistant.",
        **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        Calls an OpenAI-compatible chat completion endpoint with streaming=True
        and yields text chunks in near real time.
        
        Args:
            prompt: User prompt text
            system: System message (default assistant role)
            **kwargs: Additional parameters (temperature, max_tokens, etc.)
        
        Yields:
            str: Text chunks as they arrive from the API
        
        Raises:
            LLMClientError: If the API call fails after retries
        """
        # Check if credentials are available
        if not self.settings.llm_api_key or not self.settings.llm_base_url:
            logger.warning(
                "LLM credentials missing, falling back to stub streaming. "
                "Set LLM_API_KEY and LLM_BASE_URL in .env"
            )
            # Fallback: yield stub response
            stub_text = f"[{self.settings.llm_model}] {prompt.strip()}"
            for char in stub_text:
                yield char
                await asyncio.sleep(0.01)  # Simulate streaming delay
            return
        
        # Build OpenAI-compatible request payload
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ]
        payload: Dict[str, Any] = {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": True,  # Enable streaming
        }
        # Add optional parameters
        extra: Dict[str, Any] = {k: v for k, v in kwargs.items() if k != "system"}
        payload.update(extra)
        
        headers = {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        
        # Log request (without sensitive data)
        safe_payload = {
            "model": payload.get("model"),
            "user_message": prompt[:80],
            "stream": True,
            "temperature": payload.get("temperature"),
            "max_tokens": payload.get("max_tokens"),
        }
        logger.info(
            "LLM stream request: url=%s, payload=%s",
            self.settings.llm_base_url,
            json.dumps(safe_payload, ensure_ascii=False),
        )
        
        start_time = perf_counter()
        max_retries = 3
        base_delay = 0.5  # Base delay for exponential backoff
        
        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout) as client:
                    async with client.stream(
                        "POST",
                        self.settings.llm_base_url,
                        headers=headers,
                        json=payload,
                    ) as response:
                        # Check HTTP status
                        if response.status_code != 200:
                            error_text = await response.aread()
                            error_detail = error_text.decode('utf-8', errors='ignore')[:500]
                            logger.error(
                                "LLM stream request failed: status=%s, error=%s",
                                response.status_code,
                                error_detail,
                            )
                            if attempt < max_retries:
                                # Exponential backoff
                                delay = base_delay * (2 ** (attempt - 1))
                                logger.warning(
                                    "Retrying stream request in %.2fs (attempt %d/%d)...",
                                    delay,
                                    attempt + 1,
                                    max_retries,
                                )
                                await asyncio.sleep(delay)
                                continue
                            else:
                                raise LLMClientError(
                                    f"LLM stream request failed with status {response.status_code}: {error_detail}"
                                )
                        
                        # Process streaming response (Server-Sent Events format)
                        chunk_count = 0
                        total_text = ""
                        
                        async for line in response.aiter_lines():
                            if not line.strip():
                                continue
                            
                            # SSE format: "data: {...}" or just "{...}"
                            if line.startswith("data: "):
                                line = line[6:]  # Remove "data: " prefix
                            
                            # Skip special SSE events
                            if line.strip() == "[DONE]":
                                logger.debug("Received [DONE] signal from stream")
                                break
                            
                            try:
                                # Parse JSON chunk
                                chunk_data = json.loads(line)
                                
                                # Extract text from OpenAI-compatible format
                                text_chunk = self._extract_stream_chunk(chunk_data)
                                
                                if text_chunk:
                                    chunk_count += 1
                                    total_text += text_chunk
                                    yield text_chunk
                                    
                                    # Log first chunk for debugging
                                    if chunk_count == 1:
                                        logger.debug(
                                            "First chunk received: %s (%.2fms)",
                                            text_chunk[:50],
                                            (perf_counter() - start_time) * 1000,
                                        )
                                
                            except json.JSONDecodeError as e:
                                # Skip invalid JSON lines (might be empty or metadata)
                                logger.debug("Skipping invalid JSON line: %s", line[:100])
                                continue
                            except Exception as e:
                                # Log but don't crash on individual chunk errors
                                logger.warning(
                                    "Error processing stream chunk: %s, line=%s",
                                    e,
                                    line[:100],
                                )
                                continue
                        
                        duration_ms = (perf_counter() - start_time) * 1000
                        logger.info(
                            "LLM stream completed: %d chunks, %.1f chars, %.2f ms",
                            chunk_count,
                            len(total_text),
                            duration_ms,
                        )
                        
                        # Success - exit retry loop
                        return
                        
            except httpx.TimeoutException as exc:
                if attempt == max_retries:
                    logger.error("LLM stream request timed out after %d attempts", max_retries)
                    raise LLMClientError("LLM stream request timed out") from exc
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "LLM stream timeout on attempt %d/%d, retrying in %.2fs...",
                    attempt,
                    max_retries,
                    delay,
                )
                await asyncio.sleep(delay)
                
            except httpx.HTTPStatusError as exc:
                if attempt == max_retries:
                    logger.error("LLM stream HTTP error: %s", exc)
                    raise LLMClientError(f"LLM stream request failed: {exc}") from exc
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "LLM stream HTTP error on attempt %d/%d: %s, retrying in %.2fs...",
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                
            except httpx.RequestError as exc:
                if attempt == max_retries:
                    logger.error("LLM stream transport error: %s", exc)
                    raise LLMClientError(f"LLM stream transport error: {exc}") from exc
                delay = base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "LLM stream transport error on attempt %d/%d: %s, retrying in %.2fs...",
                    attempt,
                    max_retries,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                
            except Exception as exc:
                # Catch-all for unexpected errors
                logger.error("Unexpected error in LLM stream: %s", exc, exc_info=True)
                if attempt == max_retries:
                    raise LLMClientError(f"Unexpected error in LLM stream: {exc}") from exc
                delay = base_delay * (2 ** (attempt - 1))
                await asyncio.sleep(delay)
        
        # Should not reach here, but just in case
        raise LLMClientError("LLM stream request failed after all retries")
    
    @staticmethod
    def _extract_stream_chunk(chunk_data: Dict[str, Any]) -> Optional[str]:
        """
        Extract text content from a streaming response chunk.
        
        Supports OpenAI-compatible format:
        {
            "choices": [{
                "delta": {
                    "content": "text chunk"
                }
            }]
        }
        
        Args:
            chunk_data: Parsed JSON chunk from stream
        
        Returns:
            Extracted text chunk, or None if no text found
        """
        # OpenAI-compatible format: choices[0].delta.content
        if "choices" in chunk_data and isinstance(chunk_data["choices"], list):
            for choice in chunk_data["choices"]:
                if isinstance(choice, dict):
                    delta = choice.get("delta", {})
                    if isinstance(delta, dict):
                        content = delta.get("content")
                        if isinstance(content, str) and content:
                            return content
                    
                    # Alternative: direct content field
                    content = choice.get("content")
                    if isinstance(content, str) and content:
                        return content
        
        # Alternative format: direct text field
        if "text" in chunk_data and isinstance(chunk_data["text"], str):
            return chunk_data["text"]
        
        # Alternative format: result field
        if "result" in chunk_data and isinstance(chunk_data["result"], str):
            return chunk_data["result"]
        
        # Alternative format: data field
        if "data" in chunk_data:
            data = chunk_data["data"]
            if isinstance(data, str):
                return data
            if isinstance(data, dict) and "text" in data:
                return data["text"]
        
        return None


def get_llm_client() -> LLMClient:
    """Get or create the global LLM client instance."""
    return LLMClient()
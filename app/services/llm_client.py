from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional
from time import perf_counter

import httpx

from app.config import get_settings

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


def get_llm_client() -> LLMClient:
    return LLMClient()
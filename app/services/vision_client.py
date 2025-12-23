"""Vision model client for multi-modal analysis (V6.0.0+).

支持阿里百炼 qwen-vl-max，支持 mock 模式。
"""
from __future__ import annotations

import base64
import json
import logging
from typing import Any, Dict, Optional
from time import perf_counter

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VisionClientError(RuntimeError):
    """Raised when the vision model returns an error."""


class VisionClient:
    """Client for vision model (qwen-vl-max)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._timeout = httpx.Timeout(60.0)  # 视觉模型可能需要更长时间

    async def analyze_image(
        self,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        prompt: str = "",
        system_prompt: str = "",
    ) -> Dict[str, Any]:
        """
        分析图片并返回结构化结果。
        
        Args:
            image_url: 图片URL
            image_base64: 图片Base64编码
            prompt: 用户提示词
            system_prompt: 系统提示词
        
        Returns:
            解析后的JSON结果
        
        Raises:
            VisionClientError: 当模型调用失败时
        """
        # Mock 模式检查
        if self.settings.use_mock_vision or not self.settings.vision_api_key:
            logger.warning("[VISION] Using mock vision provider")
            return self._generate_mock_response()

        # 验证输入
        if not image_url and not image_base64:
            raise VisionClientError("image_url 和 image_base64 至少需要提供一个")

        # 准备图片内容
        image_content = self._prepare_image_content(image_url, image_base64)

        # 构建消息
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_content}},
                    {"type": "text", "text": prompt},
                ],
            },
        ]

        payload: Dict[str, Any] = {
            "model": self.settings.vision_model,
            "messages": messages,
            "temperature": 0.3,  # 降低随机性，提高一致性
        }

        headers = {
            "Authorization": f"Bearer {self.settings.vision_api_key}",
            "Content-Type": "application/json",
        }

        start = perf_counter()
        logger.info(
            "[VISION] Request: model=%s, base_url=%s",
            self.settings.vision_model,
            self.settings.vision_base_url,
        )

        try:
            response = httpx.post(
                self.settings.vision_base_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )
            logger.info(
                "[VISION] Response: status=%s, body_snippet=%s",
                response.status_code,
                response.text[:200],
            )
            response.raise_for_status()

            duration_ms = (perf_counter() - start) * 1000
            logger.info("[VISION] Request finished in %.2f ms", duration_ms)

            result = self._parse_response(response)
            return result

        except httpx.TimeoutException as exc:
            raise VisionClientError("Vision model request timed out") from exc
        except httpx.HTTPStatusError as exc:
            raise VisionClientError(f"Vision model request failed: {exc}") from exc
        except httpx.RequestError as exc:
            raise VisionClientError(f"Vision model transport error: {exc}") from exc

    def _prepare_image_content(self, image_url: Optional[str], image_base64: Optional[str]) -> str:
        """准备图片内容（URL 或 data URI）。"""
        if image_url:
            return image_url
        if image_base64:
            # 如果已经是 data URI，直接返回
            if image_base64.startswith("data:"):
                return image_base64
            # 否则转换为 data URI
            return f"data:image/jpeg;base64,{image_base64}"
        raise VisionClientError("No image provided")

    def _parse_response(self, response: httpx.Response) -> Dict[str, Any]:
        """解析模型响应为 JSON。"""
        try:
            data = response.json()
            # 阿里百炼返回格式：{"choices": [{"message": {"content": "..."}}]}
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                # 尝试解析 JSON
                try:
                    # 如果 content 是 JSON 字符串，解析它
                    if isinstance(content, str):
                        # 尝试提取 JSON（可能包含 markdown 代码块）
                        if "```json" in content:
                            json_start = content.find("```json") + 7
                            json_end = content.find("```", json_start)
                            content = content[json_start:json_end].strip()
                        elif "```" in content:
                            json_start = content.find("```") + 3
                            json_end = content.find("```", json_start)
                            content = content[json_start:json_end].strip()
                        return json.loads(content)
                    return content
                except json.JSONDecodeError:
                    logger.warning("[VISION] Failed to parse JSON from response, returning raw content")
                    return {"raw_content": content}
            raise VisionClientError("Invalid response format from vision model")
        except json.JSONDecodeError as exc:
            raise VisionClientError(f"Failed to parse response JSON: {exc}") from exc

    def _generate_mock_response(self) -> Dict[str, Any]:
        """生成 mock 响应（用于测试）。"""
        logger.info("[VISION] Generating mock response")
        return {
            "visual_summary": {
                "category_guess": "运动鞋",
                "style_impression": ["休闲", "日常"],
                "color_impression": "黑色",
                "season_impression": "四季",
                "confidence_note": "基于图片外观判断，可能存在误差（mock数据）",
            },
            "selling_points": [
                "外观看起来比较百搭",
                "整体感觉偏轻便，适合日常穿",
                "风格偏休闲，通勤或周末都合适",
            ],
            "guide_chat_copy": {
                "primary": "这双看起来比较百搭，平时走路多还是通勤穿得多一些？",
                "alternatives": [
                    "这款整体偏日常，穿着不会太累脚，你平时穿运动鞋多吗？",
                    "这双风格比较休闲，搭牛仔裤也挺合适的",
                    "从外观看感觉比较轻便，你平时更看重舒适度还是搭配？",
                ],
            },
            "confidence_level": "medium",
        }


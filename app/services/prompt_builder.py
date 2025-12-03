"""Prompt builder for copy generation."""
from __future__ import annotations

import logging
from typing import List, Optional

from app.models.product import Product
from app.schemas.copy_schemas import CopyStyle

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builder for constructing prompts for copy generation."""

    @staticmethod
    def build_copy_prompt(
        product: Product,
        style: CopyStyle,
        rag_context: Optional[List[str]] = None,
    ) -> str:
        """
        Build a prompt for copy generation.
        
        Args:
            product: Product instance
            style: Copy style (natural, professional, funny)
            rag_context: Optional RAG context chunks
        
        Returns:
            Formatted prompt string
        """
        logger.info(f"[PROMPT] Building prompt for product: {product.name}, style: {style.value}")
        
        # Extract product information
        product_name = product.name
        tags = product.tags or []
        tags_str = "、".join(tags) if tags else "时尚"
        attributes = product.attributes or {}
        color = attributes.get("color", "")
        scene = attributes.get("scene", "")
        material = attributes.get("material", "")
        price = product.price
        
        # Style descriptions
        style_descriptions = {
            CopyStyle.natural: "自然、亲切、日常，像朋友推荐一样",
            CopyStyle.professional: "专业、权威、可信，突出品质和认证",
            CopyStyle.funny: "幽默、有趣、轻松，让人忍不住想笑",
        }
        style_desc = style_descriptions.get(style, style_descriptions[CopyStyle.natural])
        
        # Build prompt
        prompt_parts = []
        
        # System context (RAG if available)
        if rag_context:
            prompt_parts.append("## 相关商品信息：")
            for i, chunk in enumerate(rag_context[:3], 1):
                prompt_parts.append(f"{i}. {chunk}")
            prompt_parts.append("")
        
        # Product information
        prompt_parts.append("## 商品信息：")
        prompt_parts.append(f"商品名称：{product_name}")
        if tags:
            prompt_parts.append(f"商品标签：{tags_str}")
        if color:
            prompt_parts.append(f"颜色：{color}")
        if scene:
            prompt_parts.append(f"适用场景：{scene}")
        if material:
            prompt_parts.append(f"材质：{material}")
        if price:
            prompt_parts.append(f"价格：{price}元")
        prompt_parts.append("")
        
        # Task description
        prompt_parts.append("## 任务要求：")
        prompt_parts.append("请为以上商品写一条朋友圈文案。")
        prompt_parts.append("")
        prompt_parts.append("要求：")
        prompt_parts.append(f"1. 风格：{style_desc}")
        prompt_parts.append("2. 长度：30-50字")
        prompt_parts.append("3. 要有吸引力，能引起购买欲望")
        prompt_parts.append("4. 语言自然流畅，符合朋友圈风格")
        prompt_parts.append("5. 突出商品的核心卖点和特色")
        if rag_context:
            prompt_parts.append("6. 可以参考相关商品信息，但要突出当前商品的独特性")
        prompt_parts.append("")
        prompt_parts.append("只输出文案内容，不要其他说明：")
        
        prompt = "\n".join(prompt_parts)
        
        logger.info(f"[PROMPT] ✓ Prompt built ({len(prompt)} chars, RAG context: {len(rag_context) if rag_context else 0} chunks)")
        logger.debug(f"[PROMPT] Prompt preview: {prompt[:200]}...")
        
        return prompt

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        Estimate token count for a text (rough approximation).
        
        For Chinese: ~1.5 chars per token
        For English: ~4 chars per token
        Mixed: use average
        
        Args:
            text: Input text
        
        Returns:
            Estimated token count
        """
        # Simple estimation: Chinese characters count more
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        
        # Rough estimation
        tokens = int(chinese_chars / 1.5 + other_chars / 4)
        return max(tokens, 1)  # At least 1 token


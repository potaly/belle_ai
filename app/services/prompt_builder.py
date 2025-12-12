"""Prompt builder for copy generation with strict factual grounding.

重构说明：
- 明确指示 LLM：当前商品信息是唯一的事实来源
- RAG 内容仅用于表达方式或背景知识，不能引入新的事实
- 严格禁止使用 RAG 中的价格、SKU、材质等具体信息
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from app.models.product import Product
from app.schemas.copy_schemas import CopyStyle

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Builder for constructing prompts for copy generation with strict factual grounding."""

    @staticmethod
    def build_copy_prompt(
        product: Product,
        style: CopyStyle,
        rag_context: Optional[List[str]] = None,
    ) -> str:
        """
        构建文案生成提示（严格事实基础）。
        
        核心原则：
        1. 当前商品信息是唯一的事实来源
        2. RAG 内容仅用于表达方式或背景知识
        3. LLM 绝不能引入产品数据中没有的事实
        
        Args:
            product: Product instance (唯一事实来源)
            style: Copy style (natural, professional, funny)
            rag_context: Optional RAG context chunks (仅用于表达参考)
        
        Returns:
            Formatted prompt string with strict grounding instructions
        """
        logger.info(f"[PROMPT] Building prompt for product: {product.name}, style: {style.value}")
        
        # Extract product information (唯一事实来源)
        product_name = product.name
        tags = product.tags or []
        tags_str = "、".join(tags) if tags else "时尚"
        attributes = product.attributes or {}
        color = attributes.get("color", "")
        scene = attributes.get("scene", "")
        material = attributes.get("material", "")
        price = product.price
        sku = product.sku
        
        # Style descriptions
        style_descriptions = {
            CopyStyle.natural: "自然、亲切、日常，像朋友推荐一样",
            CopyStyle.professional: "专业、权威、可信，突出品质和认证",
            CopyStyle.funny: "幽默、有趣、轻松，让人忍不住想笑",
        }
        style_desc = style_descriptions.get(style, style_descriptions[CopyStyle.natural])
        
        # Build prompt
        prompt_parts = []
        
        # System context (RAG if available) - 仅用于表达参考
        if rag_context:
            prompt_parts.append("## 参考信息（仅用于表达方式参考，禁止使用其中的事实信息）：")
            prompt_parts.append(
                "以下是一些相似商品的描述，**仅作为表达方式的参考**，帮助你理解如何描述商品特点。"
            )
            prompt_parts.append("")
            prompt_parts.append("**⚠️ 严格禁止事项：**")
            prompt_parts.append("1. **禁止**使用参考信息中的价格、SKU、材质等具体事实信息")
            prompt_parts.append("2. **禁止**将参考信息中的商品特征混入当前商品")
            prompt_parts.append("3. **禁止**使用参考信息中的任何数字、规格、型号")
            prompt_parts.append("4. **只能**参考表达方式和描述风格，不能参考具体内容")
            prompt_parts.append("")
            prompt_parts.append("参考信息（已过滤所有 SKU 和价格信息，仅保留描述性内容）：")
            prompt_parts.append("")
            
            for i, chunk in enumerate(rag_context[:3], 1):
                # 严格清理：移除所有 SKU 标记和价格信息
                cleaned_chunk = chunk
                # 移除 SKU 标记（所有格式）
                cleaned_chunk = re.sub(r'\[SKU:[^\]]+\]', '', cleaned_chunk)
                cleaned_chunk = re.sub(r'SKU:\s*[A-Z0-9]+', '', cleaned_chunk, flags=re.IGNORECASE)
                # 移除价格信息
                cleaned_chunk = re.sub(r'价格为?\s*\d+\.?\d*\s*元', '', cleaned_chunk)
                cleaned_chunk = re.sub(r'\d+\.?\d*\s*元', '', cleaned_chunk)
                # 移除其他可能的数字规格
                cleaned_chunk = re.sub(r'型号[：:]\s*[A-Z0-9]+', '', cleaned_chunk, flags=re.IGNORECASE)
                cleaned_chunk = cleaned_chunk.strip()
                
                if cleaned_chunk:
                    prompt_parts.append(f"{i}. {cleaned_chunk}")
            
            prompt_parts.append("")
            prompt_parts.append("---")
            prompt_parts.append("")
        
        # Product information (唯一事实来源)
        prompt_parts.append("## 商品信息（唯一事实来源）：")
        prompt_parts.append(f"商品名称：{product_name}")
        if sku:
            prompt_parts.append(f"商品SKU：{sku}")
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
        prompt_parts.append("**重要：以上商品信息是唯一的事实来源，所有文案内容必须基于这些信息。**")
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
        prompt_parts.append("")
        prompt_parts.append("**严格约束：**")
        prompt_parts.append("1. 文案中的所有事实信息（价格、SKU、材质、颜色等）必须来自上面的'商品信息'部分")
        prompt_parts.append("2. 如果参考信息中有相似描述，只能参考表达方式，不能使用其中的具体事实")
        prompt_parts.append("3. 禁止引入任何商品信息中没有的内容（如其他商品的价格、材质等）")
        prompt_parts.append("4. 确保文案中的价格、SKU、材质等信息与商品信息完全一致")
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

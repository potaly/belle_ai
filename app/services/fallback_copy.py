"""Fallback copy generation using rule-based templates.

当 LLM 失败或输出违反规则时，使用规则驱动的模板生成安全、确定性的文案。
"""
from __future__ import annotations

import logging
from typing import Dict, Optional

from app.models.product import Product

logger = logging.getLogger(__name__)

# Intent levels
INTENT_HIGH = "high"
INTENT_MEDIUM = "medium"
INTENT_LOW = "low"
INTENT_HESITATING = "hesitating"


def generate_fallback_copy(
    product: Product,
    intent_level: str,
    max_length: int = 45,
) -> str:
    """
    使用规则模板生成降级文案（确定性、安全）。
    
    业务规则：
    - 基于商品事实，不编造
    - 根据 intent_level 使用不同模板
    - 确保输出安全可控
    
    Args:
        product: 商品信息
        intent_level: 意图级别
        max_length: 最大长度
    
    Returns:
        生成的文案
    """
    logger.info(
        f"[FALLBACK] Generating fallback copy: sku={product.sku}, "
        f"intent={intent_level}, max_length={max_length}"
    )
    
    # 提取商品信息
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "")
    scene = attributes.get("scene", "")
    material = attributes.get("material", "")
    
    # 根据 intent_level 选择模板
    template_func = {
        INTENT_HIGH: _template_high_intent,
        INTENT_HESITATING: _template_hesitating_intent,
        INTENT_MEDIUM: _template_medium_intent,
        INTENT_LOW: _template_low_intent,
    }.get(intent_level, _template_medium_intent)
    
    # 生成文案
    copy_text = template_func(product_name, tags, color, scene, material, max_length)
    
    # 确保长度符合要求
    if len(copy_text) > max_length:
        copy_text = copy_text[:max_length - 2] + "…"
    
    logger.info(f"[FALLBACK] ✓ Generated fallback copy: {copy_text} ({len(copy_text)} chars)")
    
    return copy_text


def _template_high_intent(
    product_name: str,
    tags: list,
    color: str,
    scene: str,
    material: str,
    max_length: int,
) -> str:
    """高意图模板：主动推进，询问尺码或提醒库存。"""
    # 提取关键标签
    key_tags = [t for t in tags if t in ["舒适", "百搭", "时尚", "轻便"]]
    tag_str = key_tags[0] if key_tags else "不错"
    
    # 构建基础描述
    if color:
        base = f"{color}的{product_name}，{tag_str}"
    else:
        base = f"{product_name}，{tag_str}"
    
    # 添加行动建议
    if len(base) + 10 <= max_length:
        # 可以添加尺码询问
        return f"{base}，您平时穿什么码？"
    elif len(base) + 8 <= max_length:
        # 可以添加库存提醒
        return f"{base}，库存不多"
    else:
        # 只保留基础描述
        return base[:max_length]


def _template_hesitating_intent(
    product_name: str,
    tags: list,
    color: str,
    scene: str,
    material: str,
    max_length: int,
) -> str:
    """犹豫意图模板：消除顾虑，轻量提问。"""
    # 提取关键标签
    key_tags = [t for t in tags if t in ["舒适", "百搭"]]
    tag_str = key_tags[0] if key_tags else "不错"
    
    # 构建基础描述
    if color:
        base = f"{color}的{product_name}，{tag_str}"
    else:
        base = f"{product_name}，{tag_str}"
    
    # 添加轻量提问
    if scene and len(base) + len(scene) + 5 <= max_length:
        return f"{base}，适合{scene}，您觉得呢？"
    elif len(base) + 6 <= max_length:
        return f"{base}，您觉得怎么样？"
    else:
        return base[:max_length]


def _template_medium_intent(
    product_name: str,
    tags: list,
    color: str,
    scene: str,
    material: str,
    max_length: int,
) -> str:
    """中等意图模板：场景化推荐。"""
    # 提取关键标签
    key_tags = [t for t in tags if t in ["百搭", "时尚", "舒适"]]
    tag_str = key_tags[0] if key_tags else "不错"
    
    # 构建基础描述
    if color:
        base = f"{color}的{product_name}，{tag_str}"
    else:
        base = f"{product_name}，{tag_str}"
    
    # 添加场景建议
    if scene and len(base) + len(scene) + 4 <= max_length:
        return f"{base}，适合{scene}"
    elif len(base) + 4 <= max_length:
        return f"{base}，可以看看"
    else:
        return base[:max_length]


def _template_low_intent(
    product_name: str,
    tags: list,
    color: str,
    scene: str,
    material: str,
    max_length: int,
) -> str:
    """低意图模板：轻量提醒，不施压。"""
    # 构建基础描述（保持简洁）
    if color:
        base = f"{color}的{product_name}"
    else:
        base = product_name
    
    # 添加轻量描述
    key_tags = [t for t in tags if t in ["舒适", "百搭"]]
    if key_tags and len(base) + len(key_tags[0]) + 2 <= max_length:
        return f"{base}，{key_tags[0]}"
    else:
        # 只保留基础描述，不添加任何行动号召
        return base[:max_length]


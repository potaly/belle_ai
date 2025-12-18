"""Fallback product copy generation using rule-based templates (V5.5.0+).

当 LLM 失败或输出违反规则时，使用规则驱动的模板生成安全、确定性的商品话术。

V5.8.2+ 升级：guide_chat 使用对话式骨架
- 让生成内容"像一个经验导购发的第一句话"
- 保证每一条 guide_chat 文案都能自然开启对话
- 不涉及用户行为，纯商品维度
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.models.product import Product

logger = logging.getLogger(__name__)


def generate_fallback_product_copy(
    product: Product,
    selling_points: List[str],
    scene: str = "guide_chat",
    style: str = "natural",
    max_length: int = 50,
    count: int = 2,
) -> List[str]:
    """
    使用规则模板生成降级商品话术（确定性、安全）。
    
    业务规则：
    - 基于商品事实和卖点
    - 根据场景和风格调整
    - 确保输出安全可控
    
    Args:
        product: Product instance
        selling_points: List of selling points
        scene: Target scene (guide_chat / moments / poster)
        style: Writing style (natural / professional / friendly)
        max_length: Maximum length
        count: Number of copies to generate (default 2)
    
    Returns:
        List of generated copy messages
    """
    logger.info(
        f"[FALLBACK] Generating fallback copy: sku={product.sku}, "
        f"scene={scene}, style={style}, count={count}"
    )
    
    # 提取商品信息
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "") if attributes else ""
    scene_attr = attributes.get("scene", "") if attributes else ""
    
    # 选择关键卖点（最多 2 个）
    key_points = selling_points[:2] if selling_points else []
    
    # 根据场景和风格生成
    messages = []
    
    if scene == "guide_chat":
        messages = _generate_guide_chat_copy(
            product_name, color, key_points, style, max_length
        )
    elif scene == "moments":
        messages = _generate_moments_copy(
            product_name, color, key_points, style, max_length
        )
    else:  # poster
        messages = _generate_poster_copy(
            product_name, color, key_points, style, max_length
        )
    
    # 确保数量
    while len(messages) < count:
        # 生成通用话术
        generic = _generate_generic_copy(product_name, color, tags, max_length)
        if generic not in messages:
            messages.append(generic)
    
    # 限制数量
    messages = messages[:count]
    
    # 确保长度
    final_messages = []
    for msg in messages:
        if len(msg) > max_length:
            msg = msg[: max_length - 2] + "…"
        final_messages.append(msg)
    
    logger.info(f"[FALLBACK] ✓ Generated {len(final_messages)} fallback copies")
    
    return final_messages


def _generate_guide_chat_copy(
    product_name: str,
    color: str,
    key_points: List[str],
    style: str,
    max_length: int,
) -> List[str]:
    """
    生成导购私聊话术（对话式骨架，V5.8.2+）。
    
    业务规则：
    - 使用"这款"/"这双"而非完整商品名
    - 必须是问句或包含邀请回复短语
    - 必须包含行动建议关键词
    - 不能包含弱化短语
    - 自然嵌入卖点，不列举
    """
    messages = []
    
    # 使用"这款"/"这双"而非完整商品名
    product_ref = "这双" if "鞋" in product_name else "这款"
    color_desc = f"{color}的" if color else ""
    
    # 提取关键卖点（用于自然嵌入）
    comfort_point = next((p for p in key_points if "舒适" in p or "脚感" in p or "软" in p), None)
    scene_point = next((p for p in key_points if "场景" in p or "适合" in p or "通勤" in p or "运动" in p), None)
    versatile_point = next((p for p in key_points if "百搭" in p or "时尚" in p), None)
    
    # 第一条：场景询问（自然嵌入卖点）
    if scene_point or versatile_point:
        # 场景化询问
        if scene_point and "通勤" in scene_point:
            msg = f"{product_ref}{color_desc}整体比较百搭，你平时通勤多还是运动多？我可以按场景帮你看看～"
        elif scene_point and "运动" in scene_point:
            msg = f"{product_ref}{color_desc}适合运动，你平时运动多还是日常穿得多？我按场景给你推荐～"
        else:
            msg = f"{product_ref}{color_desc}整体比较百搭，你平时通勤多还是运动多？我可以按场景帮你看看～"
    elif comfort_point:
        # 舒适度询问
        msg = f"{product_ref}{color_desc}脚感偏软，久走不累；你平时穿多少码？我帮你对一下～"
    else:
        # 通用询问
        msg = f"{product_ref}{color_desc}整体不错，你平时穿多少码？我帮你对一下～"
    
    # 确保长度
    if len(msg) > max_length:
        msg = msg[:max_length - 2] + "～"
    messages.append(msg)
    
    # 第二条：尺码或场景询问（变体）
    if comfort_point:
        # 强调舒适度 + 询问尺码
        msg2 = f"{product_ref}{color_desc}脚感不错，你平时穿多少码？我帮你对一下～"
    elif scene_point:
        # 场景推荐 + 询问
        if "通勤" in scene_point:
            msg2 = f"{product_ref}{color_desc}很多人通勤穿，你平时上班穿得多吗？我给你简单说下特点～"
        else:
            msg2 = f"{product_ref}{color_desc}适合{scene_point}，你平时会用到吗？"
    else:
        # 通用询问
        msg2 = f"{product_ref}{color_desc}如果你比较在意脚感或搭配，我可以给你简单说下这双的特点～"
    
    # 确保长度
    if len(msg2) > max_length:
        msg2 = msg2[:max_length - 2] + "～"
    messages.append(msg2)
    
    # 第三条：尺码询问（如果前两条没有尺码相关）
    if "尺码" not in messages[0] and "码" not in messages[0] and "尺码" not in messages[1] and "码" not in messages[1]:
        msg3 = f"{product_ref}{color_desc}你平时穿多少码？我帮你对一下～"
        if len(msg3) > max_length:
            msg3 = msg3[:max_length - 2] + "～"
        messages.append(msg3)
    
    # 限制数量（最多 3 条）
    return messages[:3]


def _generate_moments_copy(
    product_name: str,
    color: str,
    key_points: List[str],
    style: str,
    max_length: int,
) -> List[str]:
    """生成朋友圈话术。"""
    messages = []
    
    # 第一条：卖点突出
    if key_points:
        point = key_points[0]
        point_short = point[:15] if len(point) > 15 else point
        
        if color:
            base = f"{color}的{product_name}，{point_short}"
        else:
            base = f"{product_name}，{point_short}"
        
        if len(base) <= max_length:
            messages.append(base)
        else:
            messages.append(base[:max_length])
    else:
        if color:
            base = f"{color}的{product_name}"
        else:
            base = product_name
        messages.append(base[:max_length])
    
    # 第二条：场景推荐
    if color:
        base2 = f"{color}的{product_name}"
    else:
        base2 = product_name
    
    if len(base2) + 6 <= max_length:
        messages.append(f"{base2}，适合日常穿着")
    else:
        messages.append(base2[:max_length])
    
    return messages


def _generate_poster_copy(
    product_name: str,
    color: str,
    key_points: List[str],
    style: str,
    max_length: int,
) -> List[str]:
    """生成海报话术。"""
    messages = []
    
    # 第一条：简洁有力
    if color:
        base = f"{color}的{product_name}"
    else:
        base = product_name
    
    if key_points:
        point = key_points[0]
        point_short = point[:12] if len(point) > 12 else point
        if len(base) + len(point_short) + 2 <= max_length:
            messages.append(f"{base} | {point_short}")
        else:
            messages.append(base[:max_length])
    else:
        messages.append(base[:max_length])
    
    # 第二条：强调特点
    if color:
        base2 = f"{color}的{product_name}"
    else:
        base2 = product_name
    
    if len(base2) + 4 <= max_length:
        messages.append(f"{base2}，品质之选")
    else:
        messages.append(base2[:max_length])
    
    return messages


def _generate_generic_copy(
    product_name: str,
    color: str,
    tags: List[str],
    max_length: int,
) -> str:
    """生成通用话术。"""
    if color:
        base = f"{color}的{product_name}"
    else:
        base = product_name
    
    # 添加标签（如果有）
    if tags:
        tag = tags[0]
        if len(base) + len(tag) + 2 <= max_length:
            return f"{base}，{tag}"
    
    return base[:max_length]


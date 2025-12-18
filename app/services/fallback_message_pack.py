"""Fallback message pack generation with deterministic rotation (V5.6.0+).

当 LLM 失败或输出违反规则时，使用规则驱动的模板生成安全、确定性的消息包。
支持确定性轮换，确保策略多样性。

V5.8.0+ 升级：对话式骨架
- 让生成内容"像一个经验导购发的第一句话"
- 保证每一条 guide_chat 文案都能自然开启对话
- 基于 intent_level 和 recommended_action 的强制句式骨架
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.models.product import Product
from app.services.strategy_rotation import (
    MESSAGE_STRATEGY_ASK_CONCERN,
    MESSAGE_STRATEGY_ASK_SIZE,
    MESSAGE_STRATEGY_REASSURE_COMFORT,
    MESSAGE_STRATEGY_SCENE_RELATE,
    MESSAGE_STRATEGY_SOFT_CHECK,
    select_strategies_for_pack,
    select_message_variant,
)

logger = logging.getLogger(__name__)


def generate_fallback_message_pack(
    product: Product,
    intent_level: str,
    recommended_action: str,
    behavior_summary: Optional[Dict] = None,
    rotation_key: int = 0,
    max_length: int = 45,
    min_count: int = 3,
) -> List[dict]:
    """
    使用规则模板生成降级消息包（确定性、安全、策略多样）。
    
    业务规则：
    - 至少 min_count 条消息
    - 策略必须不同
    - 基于商品事实和行为摘要
    - 使用 rotation_key 进行确定性轮换
    
    Args:
        product: Product instance
        intent_level: Intent level
        recommended_action: Recommended action
        behavior_summary: Behavior summary (optional)
        rotation_key: Rotation key for deterministic selection
        max_length: Maximum length
        min_count: Minimum message count
    
    Returns:
        List of message dicts with 'strategy' and 'message' keys
    """
    logger.info(
        f"[FALLBACK] Generating fallback message pack: sku={product.sku}, "
        f"intent={intent_level}, action={recommended_action}, "
        f"rotation_key={rotation_key}"
    )
    
    # 提取商品信息
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "") if attributes else ""
    scene = attributes.get("scene", "") if attributes else ""
    
    # 提取行为上下文（用于行为感知消息）
    behavior_context = _extract_behavior_context(behavior_summary)
    
    # 根据 recommended_action 和 intent_level 确定策略
    strategies = select_strategies_for_pack(
        intent_level=intent_level,
        recommended_action=recommended_action,
        rotation_key=rotation_key,
        min_count=min_count,
    )
    
    # 为每个策略生成消息
    messages = []
    for i, (strategy, strategy_desc) in enumerate(strategies):
        # 选择变体索引
        variant_idx = select_message_variant(strategy, rotation_key + i, variant_count=3)
        
        # 生成消息
        message = _generate_message_by_strategy(
            strategy=strategy,
            product_name=product_name,
            color=color,
            scene=scene,
            tags=tags,
            behavior_context=behavior_context,
            intent_level=intent_level,
            variant_idx=variant_idx,
            max_length=max_length,
        )
        
        messages.append({
            "type": "primary" if i == 0 else "alternative",
            "strategy": strategy_desc,
            "message": message,
        })
    
    logger.info(f"[FALLBACK] ✓ Generated {len(messages)} fallback messages")
    
    return messages


def _extract_behavior_context(behavior_summary: Optional[Dict]) -> Dict[str, any]:
    """提取行为上下文（用于生成行为感知消息）。"""
    if not behavior_summary:
        return {}
    
    visit_count = behavior_summary.get("visit_count", 0)
    avg_stay = behavior_summary.get("avg_stay_seconds", 0)
    has_favorite = behavior_summary.get("has_favorite", False)
    has_enter_buy_page = behavior_summary.get("has_enter_buy_page", False)
    
    context = {
        "visit_count": visit_count,
        "avg_stay": avg_stay,
        "has_favorite": has_favorite,
        "has_enter_buy_page": has_enter_buy_page,
        "has_multiple_visits": visit_count >= 2,
        "has_long_stay": avg_stay >= 30,
    }
    
    return context


def _generate_message_by_strategy(
    strategy: str,
    product_name: str,
    color: str,
    scene: str,
    tags: List[str],
    behavior_context: Dict,
    intent_level: str,
    variant_idx: int,
    max_length: int,
) -> str:
    """根据策略生成消息（支持变体）。"""
    if strategy == MESSAGE_STRATEGY_ASK_CONCERN:
        return _generate_ask_concern_message(
            product_name, color, behavior_context, variant_idx, max_length
        )
    elif strategy == MESSAGE_STRATEGY_ASK_SIZE:
        return _generate_ask_size_message(
            product_name, color, behavior_context, variant_idx, max_length
        )
    elif strategy == MESSAGE_STRATEGY_REASSURE_COMFORT:
        return _generate_reassure_comfort_message(
            product_name, color, tags, behavior_context, variant_idx, max_length
        )
    elif strategy == MESSAGE_STRATEGY_SCENE_RELATE:
        return _generate_scene_relate_message(
            product_name, color, scene, behavior_context, variant_idx, max_length
        )
    else:  # MESSAGE_STRATEGY_SOFT_CHECK
        return _generate_soft_check_message(
            product_name, color, behavior_context, variant_idx, max_length
        )


def _generate_ask_concern_message(
    product_name: str,
    color: str,
    behavior_context: Dict,
    variant_idx: int,
    max_length: int,
) -> str:
    """生成询问顾虑消息（对话式骨架，V5.8.0+）。"""
    # 使用"这款"/"这双"而非完整商品名
    product_ref = "这款" if "鞋" not in product_name else "这双"
    
    variants = [
        # 变体 0：基于多次访问（hesitating 标准骨架）
        lambda: (
            f"我看你最近看了几次{product_ref}，是在纠结尺码还是脚感？我可以帮你一起看看～"
            if behavior_context.get("has_multiple_visits")
            else f"{product_ref}你是想日常穿还是运动穿？我按场景给你推荐更合适的～"
        ),
        # 变体 1：基于停留时间
        lambda: (
            f"刚刚浏览挺久{product_ref}，有什么疑问吗？我帮你看看～"
            if behavior_context.get("has_long_stay")
            else f"{product_ref}你是在纠结尺码还是脚感？我可以帮你一起看看～"
        ),
        # 变体 2：场景化询问
        lambda: f"{product_ref}你是想日常穿还是运动穿？我按场景给你推荐更合适的～",
    ]
    
    message = variants[variant_idx % len(variants)]()
    return message[:max_length]


def _generate_ask_size_message(
    product_name: str,
    color: str,
    behavior_context: Dict,
    variant_idx: int,
    max_length: int,
) -> str:
    """生成询问尺码消息（对话式骨架，V5.8.0+）。"""
    # 使用"这款"/"这双"而非完整商品名
    product_ref = "这款" if "鞋" not in product_name else "这双"
    has_enter_buy_page = behavior_context.get("has_enter_buy_page", False)
    has_multiple_visits = behavior_context.get("has_multiple_visits", False)
    
    variants = [
        # 变体 0：high intent 标准骨架（引用进入购买页）
        lambda: (
            f"我看你刚进到购买页了～你平时穿多少码？我帮你对一下更稳～"
            if has_enter_buy_page
            else f"{product_ref}你平时穿多少码？我帮你对一下更稳～"
        ),
        # 变体 1：基于多次访问
        lambda: (
            f"{product_ref}你刚刚看得挺久的，现在尺码还比较全，你要不要我帮你看看合适的码？"
            if has_multiple_visits
            else f"{product_ref}现在尺码还比较全，你要不要我帮你看看合适的码？"
        ),
        # 变体 2：友好询问
        lambda: f"{product_ref}你平时这类鞋穿多少码？脚背高不高？我帮你更准一点～",
    ]
    
    message = variants[variant_idx % len(variants)]()
    return message[:max_length]


def _generate_reassure_comfort_message(
    product_name: str,
    color: str,
    tags: List[str],
    behavior_context: Dict,
    variant_idx: int,
    max_length: int,
) -> str:
    """生成舒适度保证消息（对话式骨架，V5.8.0+）。"""
    # 使用"这款"/"这双"而非完整商品名
    product_ref = "这款" if "鞋" not in product_name else "这双"
    comfort_tags = [t for t in tags if t in ["舒适", "软底", "透气"]]
    comfort_desc = comfort_tags[0] if comfort_tags else "舒适"
    has_multiple_visits = behavior_context.get("has_multiple_visits", False)
    
    variants = [
        # 变体 0：强调舒适度（问句形式）
        lambda: f"{product_ref}{comfort_desc}，穿着很舒服，你平时穿鞋在意脚感吗？",
        # 变体 1：基于行为（hesitating 场景）
        lambda: (
            f"{product_ref}{comfort_desc}，不用担心脚感，你是在意这个吗？"
            if has_multiple_visits
            else f"{product_ref}{comfort_desc}，你是在意脚感吗？"
        ),
        # 变体 2：轻量保证（问句）
        lambda: f"{product_ref}脚感不错，你平时穿鞋在意这个吗？",
    ]
    
    message = variants[variant_idx % len(variants)]()
    return message[:max_length]


def _generate_scene_relate_message(
    product_name: str,
    color: str,
    scene: str,
    behavior_context: Dict,
    variant_idx: int,
    max_length: int,
) -> str:
    """生成场景关联消息（对话式骨架，V5.8.0+）。"""
    # 使用"这款"/"这双"而非完整商品名
    product_ref = "这款" if "鞋" not in product_name else "这双"
    has_multiple_visits = behavior_context.get("has_multiple_visits", False)
    
    variants = [
        # 变体 0：medium intent 标准骨架（场景化、轻量）
        lambda: (
            f"{product_ref}很多人通勤穿，你平时上班穿得多吗？我给你简单说下特点～"
            if scene
            else f"{product_ref}很多人日常穿，你平时穿得多吗？我给你简单说下特点～"
        ),
        # 变体 1：基于行为
        lambda: (
            f"{product_ref}适合{scene}，你平时会用到吗？我按场景给你推荐更合适的～"
            if scene and has_multiple_visits
            else f"{product_ref}适合{scene if scene else '日常'}，你平时会用到吗？"
        ),
        # 变体 2：轻量推荐（问句）
        lambda: f"{product_ref}适合{scene if scene else '日常'}，你平时穿得多吗？",
    ]
    
    message = variants[variant_idx % len(variants)]()
    return message[:max_length]


def _generate_soft_check_message(
    product_name: str,
    color: str,
    behavior_context: Dict,
    variant_idx: int,
    max_length: int,
) -> str:
    """生成轻量提醒消息（对话式骨架，V5.8.0+ - low intent）。"""
    # 使用"这款"/"这双"而非完整商品名
    product_ref = "这款" if "鞋" not in product_name else "这双"
    
    variants = [
        # 变体 0：low intent 标准骨架（非侵入式、提供帮助无期待）
        lambda: f"你如果后面想了解{product_ref}的脚感或搭配，我也可以帮你看看～",
        # 变体 1：轻量提醒（问句）
        lambda: f"{product_ref}你如果后面想了解，我也可以帮你看看～",
        # 变体 2：友好提醒（问句）
        lambda: f"{product_ref}你如果后面有疑问，我也可以帮你看看～",
    ]
    
    message = variants[variant_idx % len(variants)]()
    return message[:max_length]


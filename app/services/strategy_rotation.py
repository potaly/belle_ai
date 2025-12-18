"""Deterministic strategy rotation for message pack generation (V5.6.0+).

核心概念：
- "策略多样性"而非"句子多样性"
- 确定性轮换而非随机
- 同一用户同一商品在同一时间窗口内稳定，跨天/跨窗口可轮换
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import List, Tuple

logger = logging.getLogger(__name__)

# 推荐动作枚举（动作化）
RECOMMENDED_ACTION_ASK_CONCERN_TYPE = "ask_concern_type"  # 询问顾虑类型
RECOMMENDED_ACTION_ASK_SIZE = "ask_size"  # 尺码咨询
RECOMMENDED_ACTION_REASSURE_COMFORT = "reassure_comfort"  # 舒适度保证
RECOMMENDED_ACTION_SCENE_RELATE = "scene_relate"  # 场景关联
RECOMMENDED_ACTION_MENTION_PROMO = "mention_promo"  # 提及优惠
RECOMMENDED_ACTION_MENTION_STOCK = "mention_stock"  # 库存提醒
RECOMMENDED_ACTION_SOFT_CHECK_IN = "soft_check_in"  # 轻量提醒

ALLOWED_RECOMMENDED_ACTIONS = [
    RECOMMENDED_ACTION_ASK_CONCERN_TYPE,
    RECOMMENDED_ACTION_ASK_SIZE,
    RECOMMENDED_ACTION_REASSURE_COMFORT,
    RECOMMENDED_ACTION_SCENE_RELATE,
    RECOMMENDED_ACTION_MENTION_PROMO,
    RECOMMENDED_ACTION_MENTION_STOCK,
    RECOMMENDED_ACTION_SOFT_CHECK_IN,
]

# 消息策略枚举
MESSAGE_STRATEGY_ASK_CONCERN = "ask_concern"  # 询问顾虑
MESSAGE_STRATEGY_ASK_SIZE = "ask_size"  # 询问尺码
MESSAGE_STRATEGY_SCENE_RELATE = "scene_relate"  # 场景关联
MESSAGE_STRATEGY_REASSURE_COMFORT = "reassure_comfort"  # 舒适度保证
MESSAGE_STRATEGY_SOFT_CHECK = "soft_check"  # 轻量提醒

ALLOWED_MESSAGE_STRATEGIES = [
    MESSAGE_STRATEGY_ASK_CONCERN,
    MESSAGE_STRATEGY_ASK_SIZE,
    MESSAGE_STRATEGY_SCENE_RELATE,
    MESSAGE_STRATEGY_REASSURE_COMFORT,
    MESSAGE_STRATEGY_SOFT_CHECK,
]


def get_rotation_window(timestamp: datetime | None = None, window_hours: int = 6) -> str:
    """
    获取轮换窗口标识符。
    
    业务规则：
    - 同一窗口内输出稳定
    - 不同窗口间可轮换
    - 默认 6 小时窗口，也可使用日窗口
    
    Args:
        timestamp: 时间戳（默认当前时间）
        window_hours: 窗口小时数（默认 6，可选 24 表示日窗口）
    
    Returns:
        窗口标识符字符串（格式：YYYY-MM-DD-HH 或 YYYY-MM-DD）
    """
    if timestamp is None:
        timestamp = datetime.now()
    
    if window_hours == 24:
        # 日窗口
        return timestamp.strftime("%Y-%m-%d")
    else:
        # 小时窗口（默认 6 小时）
        window_start = timestamp - timedelta(
            hours=timestamp.hour % window_hours,
            minutes=timestamp.minute,
            seconds=timestamp.second,
            microseconds=timestamp.microsecond,
        )
        return window_start.strftime("%Y-%m-%d-%H")


def compute_rotation_key(user_id: str, sku: str, rotation_window: str) -> int:
    """
    计算轮换键（确定性哈希）。
    
    业务规则：
    - 相同 (user_id, sku, window) -> 相同键
    - 不同窗口 -> 不同键
    - 完全可重现（用于调试）
    
    Args:
        user_id: 用户 ID
        sku: 商品 SKU
        rotation_window: 轮换窗口标识符
    
    Returns:
        轮换键（整数，用于选择策略和变体）
    """
    key_string = f"{user_id}:{sku}:{rotation_window}"
    hash_obj = hashlib.md5(key_string.encode("utf-8"))
    # 使用前 8 位作为整数键
    rotation_key = int(hash_obj.hexdigest()[:8], 16)
    logger.debug(f"[ROTATION] Computed rotation key: {key_string} -> {rotation_key}")
    return rotation_key


def select_strategies_for_pack(
    intent_level: str,
    recommended_action: str,
    rotation_key: int,
    min_count: int = 3,
) -> List[Tuple[str, str]]:
    """
    为消息包选择策略（确定性轮换）。
    
    业务规则：
    - 至少 min_count 个策略（默认 3）
    - 策略必须不同（无重复）
    - 基于 recommended_action 和 intent_level
    - 使用 rotation_key 进行确定性轮换
    
    Args:
        intent_level: 意图级别
        recommended_action: 推荐动作
        rotation_key: 轮换键
        min_count: 最小策略数量
    
    Returns:
        List of (strategy, description) tuples
    """
    # 根据 recommended_action 和 intent_level 确定候选策略
    candidate_strategies = _get_candidate_strategies(intent_level, recommended_action)
    
    # 使用 rotation_key 选择策略（确定性轮换）
    selected_strategies = []
    strategy_count = len(candidate_strategies)
    
    if strategy_count == 0:
        # 降级到默认策略
        candidate_strategies = [MESSAGE_STRATEGY_SOFT_CHECK]
        strategy_count = 1
    
    # 确保至少 min_count 个策略
    if strategy_count < min_count:
        # 添加其他策略（基于 rotation_key 选择）
        all_strategies = ALLOWED_MESSAGE_STRATEGIES.copy()
        for strategy in candidate_strategies:
            if strategy in all_strategies:
                all_strategies.remove(strategy)
        
        # 使用 rotation_key 选择额外策略
        for i in range(min_count - strategy_count):
            if all_strategies:
                idx = (rotation_key + i) % len(all_strategies)
                candidate_strategies.append(all_strategies[idx])
                all_strategies.pop(idx)
    
    # 使用 rotation_key 对策略进行轮换排序
    sorted_strategies = _rotate_strategies(candidate_strategies, rotation_key)
    
    # 构建策略描述
    strategy_descriptions = {
        MESSAGE_STRATEGY_ASK_CONCERN: "询问顾虑",
        MESSAGE_STRATEGY_ASK_SIZE: "询问尺码",
        MESSAGE_STRATEGY_SCENE_RELATE: "场景推荐",
        MESSAGE_STRATEGY_REASSURE_COMFORT: "舒适度保证",
        MESSAGE_STRATEGY_SOFT_CHECK: "轻量提醒",
    }
    
    result = [
        (strategy, strategy_descriptions.get(strategy, strategy))
        for strategy in sorted_strategies[:min_count]
    ]
    
    logger.info(
        f"[ROTATION] Selected {len(result)} strategies: "
        f"{[s[0] for s in result]} (rotation_key={rotation_key})"
    )
    
    return result


def _get_candidate_strategies(intent_level: str, recommended_action: str) -> List[str]:
    """根据意图级别和推荐动作获取候选策略。"""
    # 基础映射：recommended_action -> message_strategy
    action_to_strategy = {
        RECOMMENDED_ACTION_ASK_CONCERN_TYPE: MESSAGE_STRATEGY_ASK_CONCERN,
        RECOMMENDED_ACTION_ASK_SIZE: MESSAGE_STRATEGY_ASK_SIZE,
        RECOMMENDED_ACTION_REASSURE_COMFORT: MESSAGE_STRATEGY_REASSURE_COMFORT,
        RECOMMENDED_ACTION_SCENE_RELATE: MESSAGE_STRATEGY_SCENE_RELATE,
        RECOMMENDED_ACTION_SOFT_CHECK_IN: MESSAGE_STRATEGY_SOFT_CHECK,
    }
    
    primary_strategy = action_to_strategy.get(recommended_action, MESSAGE_STRATEGY_SOFT_CHECK)
    candidates = [primary_strategy]
    
    # 根据 intent_level 添加额外候选策略
    if intent_level == "high":
        # 高意图：可以添加询问尺码、场景推荐
        if MESSAGE_STRATEGY_ASK_SIZE not in candidates:
            candidates.append(MESSAGE_STRATEGY_ASK_SIZE)
        if MESSAGE_STRATEGY_SCENE_RELATE not in candidates:
            candidates.append(MESSAGE_STRATEGY_SCENE_RELATE)
    elif intent_level == "hesitating":
        # 犹豫意图：询问顾虑、舒适度保证
        if MESSAGE_STRATEGY_ASK_CONCERN not in candidates:
            candidates.append(MESSAGE_STRATEGY_ASK_CONCERN)
        if MESSAGE_STRATEGY_REASSURE_COMFORT not in candidates:
            candidates.append(MESSAGE_STRATEGY_REASSURE_COMFORT)
    elif intent_level == "medium":
        # 中等意图：场景推荐、轻量提醒
        if MESSAGE_STRATEGY_SCENE_RELATE not in candidates:
            candidates.append(MESSAGE_STRATEGY_SCENE_RELATE)
        if MESSAGE_STRATEGY_SOFT_CHECK not in candidates:
            candidates.append(MESSAGE_STRATEGY_SOFT_CHECK)
    else:  # low
        # 低意图：只使用轻量提醒
        if MESSAGE_STRATEGY_SOFT_CHECK not in candidates:
            candidates = [MESSAGE_STRATEGY_SOFT_CHECK]
    
    return candidates


def _rotate_strategies(strategies: List[str], rotation_key: int) -> List[str]:
    """使用轮换键对策略进行轮换排序。"""
    if len(strategies) <= 1:
        return strategies
    
    # 使用 rotation_key 确定起始位置
    start_idx = rotation_key % len(strategies)
    
    # 轮换列表
    rotated = strategies[start_idx:] + strategies[:start_idx]
    
    return rotated


def select_message_variant(
    strategy: str,
    rotation_key: int,
    variant_count: int = 3,
) -> int:
    """
    选择消息变体索引（确定性）。
    
    业务规则：
    - 相同 (strategy, rotation_key) -> 相同变体
    - 不同 rotation_key -> 不同变体
    
    Args:
        strategy: 消息策略
        rotation_key: 轮换键
        variant_count: 变体数量
    
    Returns:
        变体索引（0 到 variant_count-1）
    """
    # 使用 strategy 和 rotation_key 计算变体索引
    strategy_hash = hash(strategy) % 1000
    variant_idx = (rotation_key + strategy_hash) % variant_count
    
    logger.debug(
        f"[ROTATION] Selected variant {variant_idx} for strategy {strategy} "
        f"(rotation_key={rotation_key}, variant_count={variant_count})"
    )
    
    return variant_idx


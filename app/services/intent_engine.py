"""Intent analysis engine for user behavior classification.

重构说明：
- 更贴近真实零售导购判断逻辑，宁可保守，不可激进
- high 需要强信号（进入购买页、收藏、加购物车）
- 多次访问 + 长停留 = hesitating（不是 high）
- 所有判断必须包含可读的原因说明
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Intent levels (must match constants used throughout the codebase)
INTENT_HIGH = "high"
INTENT_MEDIUM = "medium"
INTENT_LOW = "low"
INTENT_HESITATING = "hesitating"


@dataclass
class IntentResult:
    """
    意图分析结果（结构化返回类型）。
    
    确保 intent_level 永远不为 None，所有判断都有可解释的原因。
    """
    level: str  # One of: high, medium, low, hesitating
    reason: str  # Human-readable explanation (MUST be non-empty)
    
    def __post_init__(self) -> None:
        """验证结果完整性。"""
        if not self.level:
            raise ValueError("intent_level must not be None or empty")
        if self.level not in (INTENT_HIGH, INTENT_MEDIUM, INTENT_LOW, INTENT_HESITATING):
            raise ValueError(f"Invalid intent_level: {self.level}")
        if not self.reason or not self.reason.strip():
            raise ValueError("reason must be non-empty")


@dataclass
class IntentThresholds:
    """
    意图判断阈值配置（可通过环境变量调整）。
    
    默认值采用保守策略，宁可低估意图，不可高估。
    """
    # High intent: 需要强信号
    min_stay_for_high: int = 60  # 仅停留时间不足以判定 high，需要配合强信号
    min_visits_for_high_with_favorite: int = 2  # 收藏 + 多次访问才判定 high
    
    # Hesitating: 多次访问但无强信号
    min_visits_for_hesitating: int = 3  # 3次以上访问但无强信号 = hesitating
    min_stay_for_hesitating: int = 20  # 长停留 + 多次访问但无强信号 = hesitating
    
    # Medium intent: 有一定兴趣
    min_visits_for_medium: int = 2  # 2次以上访问
    min_stay_for_medium: int = 15  # 平均停留15秒以上
    
    # Low intent: 单次短暂访问
    max_stay_for_low: int = 10  # 单次访问10秒以下 = low
    
    @classmethod
    def from_settings(cls) -> IntentThresholds:
        """从环境变量加载阈值配置。"""
        try:
            settings = get_settings()
            return cls(
                min_stay_for_high=getattr(settings, "intent_min_stay_for_high", 60),
                min_visits_for_high_with_favorite=getattr(
                    settings, "intent_min_visits_for_high_with_favorite", 2
                ),
                min_visits_for_hesitating=getattr(
                    settings, "intent_min_visits_for_hesitating", 3
                ),
                min_stay_for_hesitating=getattr(
                    settings, "intent_min_stay_for_hesitating", 20
                ),
                min_visits_for_medium=getattr(settings, "intent_min_visits_for_medium", 2),
                min_stay_for_medium=getattr(settings, "intent_min_stay_for_medium", 15),
                max_stay_for_low=getattr(settings, "intent_max_stay_for_low", 10),
            )
        except Exception as e:
            logger.warning(
                f"[INTENT_ENGINE] Failed to load thresholds from settings: {e}, "
                f"using defaults"
            )
            return cls()  # 使用默认值


def classify_intent(summary: Dict) -> IntentResult:
    """
    基于行为摘要分类用户购买意图（保守策略）。
    
    核心业务规则（按优先级）：
    1. HIGH: 必须有强信号（进入购买页 OR 收藏+多次访问 OR 加购物车）
    2. HESITATING: 多次访问 + 长停留，但无强信号（不是 high）
    3. MEDIUM: 2次以上访问 + 一定停留时间，但无强信号
    4. LOW: 单次短暂访问，无任何行动
    
    原则：宁可保守，不可激进。没有强信号时，不轻易判定为 high。
    
    Args:
        summary: Behavior summary dictionary containing:
            - visit_count (int): Number of visits
            - max_stay_seconds (int): Maximum stay time in seconds
            - avg_stay_seconds (float): Average stay time in seconds
            - total_stay_seconds (int): Total stay time across all visits
            - has_enter_buy_page (bool): Whether user entered buy page
            - has_favorite (bool): Whether user favorited the product
            - has_add_to_cart (bool): Whether user added to cart (optional)
            - has_share (bool): Whether user shared the product
            - has_click_size_chart (bool): Whether user clicked size chart
            - event_types (List[str]): List of event types occurred
    
    Returns:
        IntentResult: Structured result with level and reason (level is NEVER None)
    
    Examples:
        >>> summary = {
        ...     "visit_count": 2,
        ...     "max_stay_seconds": 45,
        ...     "has_enter_buy_page": True
        ... }
        >>> result = classify_intent(summary)
        >>> result.level
        'high'
        >>> result.reason
        '用户已进入购买页面，这是强烈的购买信号...'
    """
    logger.info("[INTENT_ENGINE] ========== Intent Classification Started ==========")
    logger.info(f"[INTENT_ENGINE] Input summary: {summary}")
    
    # 加载阈值配置
    thresholds = IntentThresholds.from_settings()
    
    # 提取摘要字段（带默认值）
    visit_count = summary.get("visit_count", 0)
    max_stay_seconds = summary.get("max_stay_seconds", 0)
    avg_stay_seconds = summary.get("avg_stay_seconds", 0.0)
    total_stay_seconds = summary.get("total_stay_seconds", 0)
    has_enter_buy_page = summary.get("has_enter_buy_page", False)
    has_favorite = summary.get("has_favorite", False)
    has_add_to_cart = summary.get("has_add_to_cart", False)  # 加购物车（强信号）
    has_share = summary.get("has_share", False)
    has_click_size_chart = summary.get("has_click_size_chart", False)
    event_types = summary.get("event_types", [])
    
    logger.info(
        f"[INTENT_ENGINE] Extracted metrics: "
        f"visits={visit_count}, max_stay={max_stay_seconds}s, "
        f"avg_stay={avg_stay_seconds:.1f}s, "
        f"enter_buy_page={has_enter_buy_page}, favorite={has_favorite}, "
        f"add_to_cart={has_add_to_cart}, share={has_share}, "
        f"size_chart={has_click_size_chart}"
    )
    
    # 验证输入数据
    if visit_count == 0:
        logger.warning("[INTENT_ENGINE] No visits detected, defaulting to LOW intent")
        return IntentResult(
            level=INTENT_LOW,
            reason="未检测到访问记录，购买意向较低",
        )
    
    # 规则 1: HIGH INTENT（必须有强信号）
    # 强信号包括：进入购买页、加购物车、收藏+多次访问
    if has_enter_buy_page:
        reason = (
            f"用户已进入购买页面，这是强烈的购买信号。"
            f"访问次数：{visit_count}次，最大停留：{max_stay_seconds}秒"
        )
        logger.info(f"[INTENT_ENGINE] ✓ HIGH: {reason}")
        return IntentResult(level=INTENT_HIGH, reason=reason)
    
    if has_add_to_cart:
        reason = (
            f"用户已将商品加入购物车，显示明确的购买意向。"
            f"访问次数：{visit_count}次，最大停留：{max_stay_seconds}秒"
        )
        logger.info(f"[INTENT_ENGINE] ✓ HIGH: {reason}")
        return IntentResult(level=INTENT_HIGH, reason=reason)
    
    if has_favorite and visit_count >= thresholds.min_visits_for_high_with_favorite:
        reason = (
            f"用户访问 {visit_count} 次并收藏了商品，表明持续兴趣和购买意向。"
            f"平均停留：{avg_stay_seconds:.1f}秒"
        )
        logger.info(f"[INTENT_ENGINE] ✓ HIGH: {reason}")
        return IntentResult(level=INTENT_HIGH, reason=reason)
    
    # 规则 2: HESITATING（多次访问 + 长停留，但无强信号）
    # 核心逻辑：多次访问 + 长停留 = 犹豫（不是 high，因为没有强信号）
    has_strong_signal = has_enter_buy_page or has_add_to_cart or (
        has_favorite and visit_count >= thresholds.min_visits_for_high_with_favorite
    )
    
    if (
        visit_count >= thresholds.min_visits_for_hesitating
        and not has_strong_signal
    ):
        # 多次访问但无强信号 = hesitating
        if avg_stay_seconds >= thresholds.min_stay_for_hesitating:
            reason = (
                f"用户已访问 {visit_count} 次，平均停留 {avg_stay_seconds:.1f} 秒，"
                f"但未采取购买相关行动（未进入购买页、未加购物车、未收藏），"
                f"可能存在犹豫或需要更多信息。"
            )
        else:
            reason = (
                f"用户已访问 {visit_count} 次，但停留时间较短（平均 {avg_stay_seconds:.1f} 秒），"
                f"且未采取明确行动，可能处于犹豫状态。"
            )
        logger.info(f"[INTENT_ENGINE] ✓ HESITATING: {reason}")
        return IntentResult(level=INTENT_HESITATING, reason=reason)
    
    if (
        visit_count >= 2
        and avg_stay_seconds >= thresholds.min_stay_for_hesitating
        and not has_strong_signal
    ):
        # 2次以上访问 + 长停留但无强信号 = hesitating
        reason = (
            f"用户访问 {visit_count} 次，平均停留 {avg_stay_seconds:.1f} 秒，"
            f"显示持续关注，但未采取购买相关行动，可能处于犹豫状态。"
        )
        logger.info(f"[INTENT_ENGINE] ✓ HESITATING: {reason}")
        return IntentResult(level=INTENT_HESITATING, reason=reason)
    
    # 规则 3: MEDIUM INTENT（有一定兴趣，但无强信号）
    if (
        visit_count >= thresholds.min_visits_for_medium
        and avg_stay_seconds >= thresholds.min_stay_for_medium
        and not has_strong_signal
    ):
        reason = (
            f"用户访问 {visit_count} 次，平均停留 {avg_stay_seconds:.1f} 秒，"
            f"显示一定兴趣但尚未达到强烈购买意向。"
        )
        logger.info(f"[INTENT_ENGINE] ✓ MEDIUM: {reason}")
        return IntentResult(level=INTENT_MEDIUM, reason=reason)
    
    if visit_count == 1 and max_stay_seconds > thresholds.min_stay_for_medium:
        # 单次访问但停留时间较长，或查看了尺码表
        if has_click_size_chart:
            reason = (
                f"用户首次访问，停留 {max_stay_seconds} 秒并查看了尺码表，"
                f"显示初步兴趣。"
            )
        else:
            reason = (
                f"用户首次访问，停留 {max_stay_seconds} 秒，显示初步兴趣。"
            )
        logger.info(f"[INTENT_ENGINE] ✓ MEDIUM: {reason}")
        return IntentResult(level=INTENT_MEDIUM, reason=reason)
    
    # 规则 4: LOW INTENT（单次短暂访问，无任何行动）
    if visit_count == 1 and max_stay_seconds <= thresholds.max_stay_for_low:
        reason = (
            f"用户仅访问 1 次，停留时间仅 {max_stay_seconds} 秒，"
            f"购买意向较低。"
        )
        logger.info(f"[INTENT_ENGINE] ✓ LOW: {reason}")
        return IntentResult(level=INTENT_LOW, reason=reason)
    
    if visit_count == 1 and not has_favorite and not has_click_size_chart:
        reason = (
            f"用户仅访问 1 次，停留 {max_stay_seconds} 秒，"
            f"未采取任何行动（未收藏、未查看尺码表），购买意向较低。"
        )
        logger.info(f"[INTENT_ENGINE] ✓ LOW: {reason}")
        return IntentResult(level=INTENT_LOW, reason=reason)
    
    # 默认情况：保守策略，判定为 LOW
    reason = (
        f"用户访问 {visit_count} 次，最大停留 {max_stay_seconds} 秒，"
        f"平均停留 {avg_stay_seconds:.1f} 秒，"
        f"未检测到明确的购买信号，购买意向较低。"
    )
    logger.info(f"[INTENT_ENGINE] ✓ LOW (default): {reason}")
    logger.info("[INTENT_ENGINE] ========== Intent Classification Completed ==========")
    
    return IntentResult(level=INTENT_LOW, reason=reason)


# 向后兼容：保留旧的函数签名（返回 Tuple）
def classify_intent_legacy(summary: Dict) -> tuple[str, str]:
    """
    向后兼容的意图分类函数（返回 Tuple）。
    
    新代码应使用 classify_intent() 返回 IntentResult。
    """
    result = classify_intent(summary)
    return result.level, result.reason

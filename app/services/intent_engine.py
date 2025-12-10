"""Intent analysis engine for user behavior classification."""
from __future__ import annotations

import logging
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

# Intent levels
INTENT_HIGH = "high"
INTENT_MEDIUM = "medium"
INTENT_LOW = "low"
INTENT_HESITATING = "hesitating"


def classify_intent(summary: Dict) -> Tuple[str, str]:
    # 购买意图分析，根据行为汇总分层决策：
    # 1. 如果用户明确表现出高购买兴趣（如进入购买页、收藏、停留时长长），判定为“高意图”
    # 2. 若有多次访问、较长停留，但没有强信号，判为“中等意图”
    # 3. 若仅有短暂访问，行为较为浅尝，则为“低意图”
    # 4. 如果行为反复但犹豫不决（如频繁查看、偶有操作，但无关键动作），判为“犹豫/观望”
    """
    Classify user purchase intent based on behavior summary.
    
    This function implements a multi-rule hybrid scoring system to determine
    the user's purchase intention level. The system evaluates multiple factors
    including visit frequency, engagement depth, and action signals.
    
    Args:
        summary: Behavior summary dictionary containing:
            - visit_count (int): Number of visits
            - max_stay_seconds (int): Maximum stay time in seconds
            - avg_stay_seconds (float): Average stay time in seconds
            - total_stay_seconds (int): Total stay time across all visits
            - has_enter_buy_page (bool): Whether user entered buy page
            - has_favorite (bool): Whether user favorited the product
            - has_share (bool): Whether user shared the product
            - has_click_size_chart (bool): Whether user clicked size chart
            - event_types (List[str]): List of event types occurred
            - first_visit_time (datetime, optional): First visit timestamp
            - last_visit_time (datetime, optional): Last visit timestamp
    
    Returns:
        Tuple[str, str]: (intention_level, reason)
            - intention_level: One of "high", "medium", "low", "hesitating"
            - reason: Textual explanation of why this level was chosen
    
    Examples:
        >>> summary = {
        ...     "visit_count": 3,
        ...     "max_stay_seconds": 45,
        ...     "avg_stay_seconds": 25.0,
        ...     "has_enter_buy_page": True
        ... }
        >>> level, reason = classify_intent(summary)
        >>> level
        'high'
    """
    logger.info("[INTENT_ENGINE] ========== Intent Classification Started ==========")
    logger.info(f"[INTENT_ENGINE] Input summary: {summary}")
    
    # Extract summary fields with defaults
    visit_count = summary.get("visit_count", 0)
    max_stay_seconds = summary.get("max_stay_seconds", 0)
    avg_stay_seconds = summary.get("avg_stay_seconds", 0.0)
    total_stay_seconds = summary.get("total_stay_seconds", 0)
    has_enter_buy_page = summary.get("has_enter_buy_page", False)
    has_favorite = summary.get("has_favorite", False)
    has_share = summary.get("has_share", False)
    has_click_size_chart = summary.get("has_click_size_chart", False)
    event_types = summary.get("event_types", [])
    
    logger.info(
        f"[INTENT_ENGINE] Extracted metrics: "
        f"visits={visit_count}, max_stay={max_stay_seconds}s, "
        f"avg_stay={avg_stay_seconds:.1f}s, "
        f"enter_buy_page={has_enter_buy_page}, favorite={has_favorite}, "
        f"share={has_share}, size_chart={has_click_size_chart}"
    )
    
    # Calculate scores for different factors
    scores = _calculate_scores(
        visit_count=visit_count,
        max_stay_seconds=max_stay_seconds,
        avg_stay_seconds=avg_stay_seconds,
        total_stay_seconds=total_stay_seconds,
        has_enter_buy_page=has_enter_buy_page,
        has_favorite=has_favorite,
        has_share=has_share,
        has_click_size_chart=has_click_size_chart,
        event_types=event_types,
    )
    
    logger.info(f"[INTENT_ENGINE] Calculated scores: {scores}")
    
    # Classify intent based on scores
    intent_level, reason = _determine_intent_level(scores, summary)
    
    logger.info(
        f"[INTENT_ENGINE] ✓ Classified intent: {intent_level} - {reason}"
    )
    logger.info("[INTENT_ENGINE] ========== Intent Classification Completed ==========")
    
    return intent_level, reason


def _calculate_scores(
    visit_count: int,
    max_stay_seconds: int,
    avg_stay_seconds: float,
    total_stay_seconds: int,
    has_enter_buy_page: bool,
    has_favorite: bool,
    has_share: bool,
    has_click_size_chart: bool,
    event_types: list,
) -> Dict[str, float]:
    """
    Calculate scores for different intent factors.
    
    Returns a dictionary with scores for:
    - high_intent_signals: Strong purchase signals (enter buy page, favorite, etc.)
    - engagement_depth: How deeply user engaged (stay time, interactions)
    - visit_frequency: How often user visited
    - hesitation_signals: Signs of hesitation (repeated visits without action)
    """
    scores = {
        "high_intent_signals": 0.0,
        "engagement_depth": 0.0,
        "visit_frequency": 0.0,
        "hesitation_signals": 0.0,
    }
    
    # 1. High intent signals (strong purchase indicators)
    if has_enter_buy_page:
        scores["high_intent_signals"] += 50.0  # Entering buy page is strong signal
    if has_favorite:
        scores["high_intent_signals"] += 30.0  # Favorite indicates interest
    if has_share:
        scores["high_intent_signals"] += 20.0  # Share shows engagement
    if has_click_size_chart:
        scores["high_intent_signals"] += 15.0  # Size chart = serious consideration
    
    # 2. Engagement depth (based on stay time)
    if max_stay_seconds > 30:
        scores["engagement_depth"] += 40.0  # Long stay = high engagement
    elif max_stay_seconds > 15:
        scores["engagement_depth"] += 20.0
    elif max_stay_seconds > 6:
        scores["engagement_depth"] += 10.0
    
    if avg_stay_seconds > 20:
        scores["engagement_depth"] += 20.0  # High average stay
    elif avg_stay_seconds > 10:
        scores["engagement_depth"] += 10.0
    
    # 3. Visit frequency
    if visit_count >= 3:
        scores["visit_frequency"] += 30.0  # Multiple visits = strong interest
    elif visit_count == 2:
        scores["visit_frequency"] += 15.0
    elif visit_count == 1:
        scores["visit_frequency"] += 5.0
    
    # 4. Hesitation signals (repeated visits without high-intent actions)
    if visit_count >= 3 and not has_enter_buy_page and not has_favorite:
        # Multiple visits but no strong actions = hesitating
        scores["hesitation_signals"] += 30.0
    elif visit_count >= 2 and max_stay_seconds < 10 and not has_enter_buy_page:
        # Multiple quick visits without action = hesitating
        scores["hesitation_signals"] += 20.0
    
    return scores


def _determine_intent_level(
    scores: Dict[str, float],
    summary: Dict,
) -> Tuple[str, str]:
    """
    Determine intent level based on calculated scores.
    
    Rules (in priority order):
    1. High: enter_buy_page OR max_stay > 30s OR (visits >= 2 AND favorite)
    2. Hesitating: visits >= 3 AND no high-intent actions
    3. Medium: visits 2-3 AND avg_stay > 10s
    4. Low: visit 1 time < 6s
    """
    visit_count = summary.get("visit_count", 0)
    max_stay_seconds = summary.get("max_stay_seconds", 0)
    avg_stay_seconds = summary.get("avg_stay_seconds", 0.0)
    has_enter_buy_page = summary.get("has_enter_buy_page", False)
    has_favorite = summary.get("has_favorite", False)
    has_click_size_chart = summary.get("has_click_size_chart", False)
    
    high_intent_score = scores["high_intent_signals"]
    engagement_score = scores["engagement_depth"]
    frequency_score = scores["visit_frequency"]
    hesitation_score = scores["hesitation_signals"]
    
    # Rule 1: HIGH INTENT
    # - Entered buy page (strongest signal)
    # - OR max stay > 30 seconds (deep engagement)
    # - OR (visited 2+ times AND favorited) (repeated interest + action)
    if has_enter_buy_page:
        reason = (
            f"用户已进入购买页面，这是强烈的购买信号。"
            f"访问次数：{visit_count}次，最大停留：{max_stay_seconds}秒"
        )
        return INTENT_HIGH, reason
    
    if max_stay_seconds > 30:
        reason = (
            f"用户最大停留时间 {max_stay_seconds} 秒，显示深度关注。"
            f"访问次数：{visit_count}次，平均停留：{avg_stay_seconds:.1f}秒"
        )
        return INTENT_HIGH, reason
    
    if visit_count >= 2 and has_favorite:
        reason = (
            f"用户访问 {visit_count} 次并收藏了商品，表明持续兴趣和购买意向。"
            f"平均停留：{avg_stay_seconds:.1f}秒"
        )
        return INTENT_HIGH, reason
    
    # Rule 2: HESITATING
    # - Visited 3+ times but no high-intent actions
    # - OR visited 2+ times with short stays and no actions
    if hesitation_score >= 20.0:
        if visit_count >= 3:
            reason = (
                f"用户已访问 {visit_count} 次，但未采取购买相关行动（未进入购买页、未收藏），"
                f"可能存在犹豫或需要更多信息。平均停留：{avg_stay_seconds:.1f}秒"
            )
        else:
            reason = (
                f"用户访问 {visit_count} 次但停留时间较短（最大 {max_stay_seconds} 秒），"
                f"且未采取明确行动，可能处于犹豫状态"
            )
        return INTENT_HESITATING, reason
    
    # Rule 3: MEDIUM INTENT
    # - Visited 2-3 times AND avg stay > 10s
    # - OR visited 1 time with good engagement (stay > 15s, or multiple interactions)
    if (2 <= visit_count <= 3) and avg_stay_seconds > 10:
        reason = (
            f"用户访问 {visit_count} 次，平均停留 {avg_stay_seconds:.1f} 秒，"
            f"显示一定兴趣但尚未达到强烈购买意向"
        )
        return INTENT_MEDIUM, reason
    
    if visit_count == 1 and (max_stay_seconds > 15 or has_click_size_chart):
        reason = (
            f"用户首次访问，停留 {max_stay_seconds} 秒"
            f"{'，查看了尺码表' if has_click_size_chart else ''}，"
            f"显示初步兴趣"
        )
        return INTENT_MEDIUM, reason
    
    # Rule 4: LOW INTENT
    # - Single visit < 6 seconds
    # - OR single visit with very low engagement
    if visit_count == 1 and max_stay_seconds < 6:
        reason = (
            f"用户仅访问 1 次，停留时间仅 {max_stay_seconds} 秒，"
            f"购买意向较低"
        )
        return INTENT_LOW, reason
    
    if visit_count == 1 and max_stay_seconds < 15 and not has_favorite:
        reason = (
            f"用户仅访问 1 次，停留 {max_stay_seconds} 秒，"
            f"未采取任何行动，购买意向较低"
        )
        return INTENT_LOW, reason
    
    # Default: Use score-based classification
    total_score = high_intent_score + engagement_score + frequency_score - hesitation_score
    
    if total_score >= 60:
        reason = (
            f"综合评分 {total_score:.1f} 分（高意图信号：{high_intent_score:.1f}，"
            f"参与度：{engagement_score:.1f}，访问频率：{frequency_score:.1f}），"
            f"显示较高购买意向"
        )
        return INTENT_HIGH, reason
    elif total_score >= 30:
        reason = (
            f"综合评分 {total_score:.1f} 分，显示中等购买意向。"
            f"访问 {visit_count} 次，平均停留 {avg_stay_seconds:.1f} 秒"
        )
        return INTENT_MEDIUM, reason
    elif hesitation_score > 0:
        reason = (
            f"综合评分 {total_score:.1f} 分，犹豫信号 {hesitation_score:.1f} 分，"
            f"用户可能处于犹豫状态"
        )
        return INTENT_HESITATING, reason
    else:
        reason = (
            f"综合评分 {total_score:.1f} 分，购买意向较低。"
            f"访问 {visit_count} 次，最大停留 {max_stay_seconds} 秒"
        )
        return INTENT_LOW, reason


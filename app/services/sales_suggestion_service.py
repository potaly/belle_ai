"""Sales suggestion pack generation service (V5.4.0+).

将输出从"一句话"升级为"导购可执行建议包"：
- recommended_action（动作类型）
- why_now（时机解释）
- send_recommendation（建议发/不建议发 + 置信度）
- message_pack（2~3条候选话术）
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from app.agents.context import AgentContext
from app.core.config import get_settings
from app.models.product import Product
from app.services.fallback_copy import generate_fallback_copy
from app.services.fallback_message_pack import generate_fallback_message_pack
from app.services.llm_client import LLMClientError, get_llm_client
from app.services.message_validators import validate_message_pack
from app.services.prompt_templates import (
    FORBIDDEN_MARKETING_WORDS,
    build_system_prompt,
    build_user_prompt,
    validate_copy_output,
)
from app.services.strategy_rotation import (
    MESSAGE_STRATEGY_ASK_CONCERN,
    MESSAGE_STRATEGY_ASK_SIZE,
    MESSAGE_STRATEGY_REASSURE_COMFORT,
    MESSAGE_STRATEGY_SCENE_RELATE,
    MESSAGE_STRATEGY_SOFT_CHECK,
    compute_rotation_key,
    get_rotation_window,
    select_message_variant,
    select_strategies_for_pack,
)

logger = logging.getLogger(__name__)

# Recommended action types (V5.6.0+ - action-oriented)
ACTION_ASK_CONCERN_TYPE = "ask_concern_type"  # 询问顾虑类型
ACTION_ASK_SIZE = "ask_size"  # 尺码咨询
ACTION_REASSURE_COMFORT = "reassure_comfort"  # 舒适度保证
ACTION_SCENE_RELATE = "scene_relate"  # 场景关联
ACTION_MENTION_PROMO = "mention_promo"  # 提及优惠
ACTION_MENTION_STOCK = "mention_stock"  # 库存提醒
ACTION_SOFT_CHECK_IN = "soft_check_in"  # 轻量提醒

# Legacy action (for backward compatibility)
ACTION_SCENE_RECOMMENDATION = ACTION_SCENE_RELATE

ALLOWED_ACTIONS = [
    ACTION_ASK_CONCERN_TYPE,
    ACTION_ASK_SIZE,
    ACTION_REASSURE_COMFORT,
    ACTION_SCENE_RELATE,
    ACTION_MENTION_PROMO,
    ACTION_MENTION_STOCK,
    ACTION_SOFT_CHECK_IN,
]

# Intent levels
INTENT_HIGH = "high"
INTENT_MEDIUM = "medium"
INTENT_LOW = "low"
INTENT_HESITATING = "hesitating"


@dataclass
class MessageItem:
    """Message item in message pack."""
    
    type: str  # "primary" or "alternative"
    strategy: str  # Strategy description
    message: str  # Message content


@dataclass
class SendRecommendation:
    """Send recommendation with risk assessment (V5.6.0+)."""
    
    suggested: bool  # Whether to send
    best_timing: str  # Best timing (e.g., "now", "within 30 minutes", "tonight 19-21")
    note: str  # Short operational note
    risk_level: str  # "low", "medium", or "high"
    next_step: str  # What the guide should do after customer replies


@dataclass
class FollowupPlaybookItem:
    """Follow-up playbook item for guides (V5.8.0+)."""
    
    condition: str  # Customer response condition (e.g., "顾客说尺码不确定")
    reply: str  # Suggested reply message


@dataclass
class SalesSuggestion:
    """Sales suggestion pack for store guides."""
    
    intent_level: str
    confidence: str  # "high", "medium", or "low"
    why_now: str  # Human readable explanation
    recommended_action: str  # Action type
    action_explanation: str  # Explain recommended_action
    message_pack: List[MessageItem]  # 3+ messages with different strategies
    send_recommendation: SendRecommendation
    followup_playbook: List[FollowupPlaybookItem]  # V5.8.0+: Guide next-step SOP


def choose_recommended_action(
    intent_level: str,
    behavior_summary: Optional[Dict] = None,
    product: Optional[Product] = None,
) -> tuple[str, str]:
    """
    根据意图级别和行为特征选择推荐动作。
    
    Args:
        intent_level: Intent level (high/hesitating/medium/low)
        behavior_summary: Behavior summary (optional)
        product: Product instance (optional)
    
    Returns:
        Tuple of (action_type, action_explanation)
    """
    has_click_size_chart = False
    has_favorite = False
    visit_count = 0
    
    if behavior_summary:
        has_click_size_chart = behavior_summary.get("has_click_size_chart", False)
        has_favorite = behavior_summary.get("has_favorite", False)
        visit_count = behavior_summary.get("visit_count", 0)
    
    # 根据意图级别和行为特征选择动作
    if intent_level == INTENT_HIGH:
        if has_click_size_chart:
            return (
                ACTION_ASK_SIZE,
                "用户已查看尺码表，建议主动询问尺码以推进购买",
            )
        elif has_favorite:
            return (
                ACTION_MENTION_STOCK,
                "用户已收藏商品，建议提醒库存情况以促进下单",
            )
        else:
            return (
                ACTION_ASK_SIZE,
                "用户购买意图强烈，建议询问尺码以推进购买",
            )
    
    elif intent_level == INTENT_HESITATING:
        if visit_count >= 3:
            return (
                ACTION_ASK_CONCERN_TYPE,
                "用户多次访问但未下单，可能存在顾虑，建议询问顾虑类型",
            )
        else:
            return (
                ACTION_SCENE_RELATE,
                "用户处于犹豫状态，建议通过场景推荐消除顾虑",
            )
    
    elif intent_level == INTENT_MEDIUM:
        scene = ""
        if product and product.attributes:
            scene = product.attributes.get("scene", "")
        if scene:
            return (
                ACTION_SCENE_RELATE,
                f"用户有一定兴趣，建议推荐{scene}场景使用",
            )
        else:
            return (
                ACTION_REASSURE_COMFORT,
                "用户有一定兴趣，建议强调舒适度以增强信心",
            )
    
    else:  # INTENT_LOW
        return (
            ACTION_SOFT_CHECK_IN,
            "用户兴趣较低，建议轻量提醒，不施压",
        )


def build_why_now(
    intent_level: str,
    intent_reason: str,
    behavior_summary: Optional[Dict] = None,
) -> str:
    """
    构建"为什么现在找这位顾客"的时机解释。
    
    Args:
        intent_level: Intent level
        intent_reason: Intent classification reason
        behavior_summary: Behavior summary (optional)
    
    Returns:
        Human readable explanation
    """
    parts = []
    
    # 基于意图原因
    if intent_reason:
        parts.append(intent_reason)
    
    # 基于行为特征补充
    if behavior_summary:
        visit_count = behavior_summary.get("visit_count", 0)
        has_favorite = behavior_summary.get("has_favorite", False)
        has_enter_buy_page = behavior_summary.get("has_enter_buy_page", False)
        
        if visit_count >= 3:
            parts.append(f"用户已访问 {visit_count} 次，表现出持续关注")
        elif visit_count >= 2:
            parts.append(f"用户已访问 {visit_count} 次，有一定兴趣")
        
        if has_favorite:
            parts.append("用户已收藏商品")
        
        if has_enter_buy_page:
            parts.append("用户已进入购买页面")
    
    if not parts:
        parts.append("用户浏览了商品")
    
    return "；".join(parts)


def calculate_confidence(
    intent_level: str,
    behavior_summary: Optional[Dict] = None,
) -> str:
    """
    计算置信度（high/medium/low）。
    
    Args:
        intent_level: Intent level
        behavior_summary: Behavior summary (optional)
    
    Returns:
        Confidence level ("high", "medium", or "low")
    """
    # 基础置信度（基于意图级别）
    base_confidence = {
        INTENT_HIGH: "high",
        INTENT_HESITATING: "medium",
        INTENT_MEDIUM: "medium",
        INTENT_LOW: "low",
    }.get(intent_level, "low")
    
    # 根据行为特征调整
    if behavior_summary:
        has_favorite = behavior_summary.get("has_favorite", False)
        has_enter_buy_page = behavior_summary.get("has_enter_buy_page", False)
        visit_count = behavior_summary.get("visit_count", 0)
        
        # 强信号提升置信度
        if has_favorite or has_enter_buy_page:
            if base_confidence == "medium":
                return "high"
            elif base_confidence == "low":
                return "medium"
        
        # 多次访问提升置信度
        if visit_count >= 3 and base_confidence == "low":
            return "medium"
    
    return base_confidence


def build_send_recommendation(
    intent_level: str,
    confidence: str,
    allowed: bool,
    recommended_action: str,
) -> SendRecommendation:
    """
    构建发送建议（V5.6.0+ - 包含 best_timing 和 next_step）。
    
    Args:
        intent_level: Intent level
        confidence: Confidence level
        allowed: Whether anti-disturb check passed
        recommended_action: Recommended action type
    
    Returns:
        SendRecommendation instance
    """
    from datetime import datetime
    
    current_hour = datetime.now().hour
    
    if not allowed:
        return SendRecommendation(
            suggested=False,
            best_timing="not_recommended",
            note="反打扰检查未通过，不建议主动联系",
            risk_level="high",
            next_step="等待用户主动联系或系统提示",
        )
    
    if intent_level == INTENT_LOW:
        return SendRecommendation(
            suggested=False,
            best_timing="tonight 19-21" if current_hour < 19 else "tomorrow 10-12",
            note="用户兴趣较低，主动联系可能造成打扰",
            risk_level="medium",
            next_step="观察用户后续行为，等待更合适的时机",
        )
    
    if confidence == "high":
        # 高置信度：立即发送或30分钟内
        timing = "now" if 9 <= current_hour <= 21 else "within 30 minutes"
        next_step_map = {
            ACTION_ASK_SIZE: "根据用户回复的尺码，推荐合适款式",
            ACTION_ASK_CONCERN_TYPE: "根据用户顾虑类型，提供针对性解答",
            ACTION_REASSURE_COMFORT: "进一步强调舒适度，提供试穿建议",
            ACTION_SCENE_RELATE: "根据用户使用场景，推荐搭配方案",
            ACTION_MENTION_STOCK: "确认库存后，引导下单",
            ACTION_MENTION_PROMO: "提供优惠详情，促进转化",
            ACTION_SOFT_CHECK_IN: "根据用户回复，判断是否需要进一步跟进",
        }
        return SendRecommendation(
            suggested=True,
            best_timing=timing,
            note="用户购买意图明确，建议主动联系",
            risk_level="low",
            next_step=next_step_map.get(recommended_action, "根据用户回复灵活应对"),
        )
    elif confidence == "medium":
        # 中等置信度：30分钟内或今晚
        timing = "within 30 minutes" if 9 <= current_hour <= 20 else "tonight 19-21"
        return SendRecommendation(
            suggested=True,
            best_timing=timing,
            note="用户有一定兴趣，可以尝试联系",
            risk_level="low",
            next_step="根据用户回复判断购买意愿，决定是否继续跟进",
        )
    else:  # confidence == "low"
        return SendRecommendation(
            suggested=False,
            best_timing="tonight 19-21" if current_hour < 19 else "tomorrow 10-12",
            note="用户兴趣较低，建议观察后再联系",
            risk_level="medium",
            next_step="观察用户后续行为，等待更合适的时机",
        )


async def generate_message_pack(
    product: Product,
    intent_level: str,
    intent_reason: str,
    recommended_action: str,
    behavior_summary: Optional[Dict] = None,
    max_length: Optional[int] = None,
    user_id: Optional[str] = None,
    rotation_window: Optional[str] = None,
) -> List[MessageItem]:
    """
    生成消息包（V5.6.0+ - 策略多样、行为感知、确定性轮换）。
    
    业务规则：
    - 至少 3 条消息，策略必须不同
    - 每条消息必须包含行动建议关键词
    - 必须引用顾客上下文（基于行为摘要）
    - 禁止营销词汇
    - 基于商品事实，不串货
    - 确定性轮换：同一窗口内稳定，跨窗口可轮换
    
    Args:
        product: Product instance
        intent_level: Intent level
        intent_reason: Intent classification reason
        recommended_action: Recommended action type
        behavior_summary: Behavior summary (optional)
        max_length: Maximum length (default from config)
        user_id: User ID (for deterministic rotation)
        rotation_window: Rotation window identifier (optional)
    
    Returns:
        List of MessageItem (at least 3 messages with different strategies)
    """
    settings = get_settings()
    max_length = max_length or settings.copy_max_length
    
    # 计算轮换键（确定性）
    if rotation_window is None:
        rotation_window = get_rotation_window()
    if user_id:
        rotation_key = compute_rotation_key(user_id, product.sku, rotation_window)
    else:
        rotation_key = 0  # 降级：无轮换
    
    logger.info(
        f"[SUGGESTION] Generating message pack (V5.6.0+): action={recommended_action}, "
        f"intent={intent_level}, rotation_key={rotation_key}, window={rotation_window}"
    )
    
    # 选择策略（确定性轮换）
    strategies = select_strategies_for_pack(
        intent_level=intent_level,
        recommended_action=recommended_action,
        rotation_key=rotation_key,
        min_count=3,
    )
    
    # 尝试使用 LLM 生成消息包
    messages: List[MessageItem] = []
    llm_used = False
    
    try:
        llm_client = get_llm_client()
        if llm_client.settings.llm_api_key and llm_client.settings.llm_base_url:
            # 构建提示词（要求生成策略多样的消息）
            system_prompt = build_system_prompt()
            user_prompt = _build_message_pack_prompt_v2(
                product=product,
                intent_level=intent_level,
                intent_reason=intent_reason,
                strategies=strategies,
                behavior_summary=behavior_summary,
                max_length=max_length,
            )
            
            logger.info("[SUGGESTION] Calling LLM to generate strategy-diverse message pack...")
            
            full_response = ""
            async for chunk in llm_client.stream_chat(
                user_prompt,
                system=system_prompt,
                temperature=0.7,  # Lower temperature for more controlled output
                max_tokens=400,  # More tokens for multiple strategies
            ):
                if chunk:
                    full_response += chunk
            
            # 解析 LLM 响应（按策略分配）
            parsed_messages_by_strategy = _parse_llm_message_pack_by_strategy(
                full_response, strategies, rotation_key
            )
            
            # 构建消息包
            for i, (strategy, strategy_desc) in enumerate(strategies):
                if strategy in parsed_messages_by_strategy:
                    msg_text = parsed_messages_by_strategy[strategy]
                    # 验证消息
                    from app.services.message_validators import validate_message
                    
                    # Primary 消息需要特殊验证（V5.8.0+）
                    is_primary = i == 0
                    if is_primary:
                        from app.services.message_validators import validate_primary_message
                        
                        is_valid, error = validate_primary_message(
                            message=msg_text,
                            current_sku=product.sku,
                            product_name=product.name,
                            recommended_action=recommended_action,
                            max_length=max_length,
                        )
                    else:
                        from app.services.message_validators import validate_message
                        
                        is_valid, error = validate_message(
                            message=msg_text,
                            current_sku=product.sku,
                            max_length=max_length,
                            require_action_hint=True,
                        )
                    if is_valid:
                        messages.append(
                            MessageItem(
                                type="primary" if i == 0 else "alternative",
                                strategy=strategy_desc,
                                message=msg_text,
                            )
                        )
                    else:
                        logger.warning(
                            f"[SUGGESTION] LLM message validation failed for strategy {strategy}: {error}"
                        )
            
            # 验证消息包
            if len(messages) >= 3:
                message_pack_dict = [
                    {"strategy": msg.strategy, "message": msg.message} for msg in messages
                ]
                from app.services.message_validators import validate_message_pack
                
                is_valid_pack, pack_error = validate_message_pack(
                    message_pack=message_pack_dict,
                    current_sku=product.sku,
                    max_length=max_length,
                    min_count=3,
                )
                if is_valid_pack:
                    llm_used = True
                    logger.info(f"[SUGGESTION] ✓ LLM generated {len(messages)} strategy-diverse messages")
                else:
                    logger.warning(f"[SUGGESTION] Message pack validation failed: {pack_error}")
            else:
                logger.warning(
                    f"[SUGGESTION] LLM generated insufficient messages ({len(messages)}), "
                    f"falling back to templates"
                )
                
    except LLMClientError as e:
        logger.warning(f"[SUGGESTION] ⚠ LLM error: {e}, falling back to templates")
    except Exception as e:
        logger.error(
            f"[SUGGESTION] ✗ Unexpected error during LLM generation: {e}",
            exc_info=True,
        )
    
    # 降级到规则模板（使用确定性轮换）
    if not messages or not llm_used:
        logger.info("[SUGGESTION] Using fallback templates with deterministic rotation...")
        fallback_messages = generate_fallback_message_pack(
            product=product,
            intent_level=intent_level,
            recommended_action=recommended_action,
            behavior_summary=behavior_summary,
            rotation_key=rotation_key,
            max_length=max_length,
            min_count=3,
        )
        
        # 转换为 MessageItem
        for msg_dict in fallback_messages:
            messages.append(
                MessageItem(
                    type=msg_dict["type"],
                    strategy=msg_dict["strategy"],
                    message=msg_dict["message"],
                )
            )
        
        # 验证 Primary 消息（V5.8.0+）
        if messages:
            primary_msg = messages[0]
            from app.services.message_validators import validate_primary_message
            
            is_valid, error = validate_primary_message(
                message=primary_msg.message,
                current_sku=product.sku,
                product_name=product.name,
                recommended_action=recommended_action,
                max_length=max_length,
            )
            if not is_valid:
                logger.warning(
                    f"[SUGGESTION] Fallback primary message validation failed: {error}, "
                    f"regenerating..."
                )
                # 重新生成 Primary 消息（使用第一个策略）
                if strategies:
                    strategy, strategy_desc = strategies[0]
                    variant_idx = select_message_variant(strategy, rotation_key, variant_count=3)
                    # 使用 fallback 函数重新生成
                    from app.services.fallback_message_pack import _generate_message_by_strategy
                    from app.services.fallback_message_pack import _extract_behavior_context
                    
                    behavior_context = _extract_behavior_context(behavior_summary)
                    product_name = product.name
                    tags = product.tags or []
                    attributes = product.attributes or {}
                    color = attributes.get("color", "") if attributes else ""
                    scene = attributes.get("scene", "") if attributes else ""
                    
                    new_primary = _generate_message_by_strategy(
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
                    messages[0].message = new_primary
        
        logger.info(f"[SUGGESTION] ✓ Fallback generated {len(messages)} strategy-diverse messages")
    
    return messages


def _build_message_pack_prompt_v2(
    product: Product,
    intent_level: str,
    intent_reason: str,
    strategies: List[tuple],
    behavior_summary: Optional[Dict] = None,
    max_length: int = 45,
) -> str:
    """构建生成策略多样消息包的提示词（V5.6.0+）。"""
    # 提取商品信息
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "") if attributes else ""
    scene = attributes.get("scene", "") if attributes else ""
    
    # 构建行为上下文（必须引用）
    behavior_context_parts = []
    if behavior_summary:
        visit_count = behavior_summary.get("visit_count", 0)
        avg_stay = behavior_summary.get("avg_stay_seconds", 0)
        has_favorite = behavior_summary.get("has_favorite", False)
        
        if visit_count >= 2:
            behavior_context_parts.append(f"用户已访问 {visit_count} 次")
        if avg_stay >= 30:
            behavior_context_parts.append("用户停留时间较长")
        if has_favorite:
            behavior_context_parts.append("用户已收藏")
    
    behavior_context = "；".join(behavior_context_parts) if behavior_context_parts else "用户浏览了商品"
    
    # 策略说明
    strategy_descriptions = {
        MESSAGE_STRATEGY_ASK_CONCERN: "询问顾虑（如'有什么顾虑吗？'）",
        MESSAGE_STRATEGY_ASK_SIZE: "询问尺码（如'您平时穿什么码？'）",
        MESSAGE_STRATEGY_REASSURE_COMFORT: "舒适度保证（如'穿着很舒服'）",
        MESSAGE_STRATEGY_SCENE_RELATE: "场景推荐（如'适合XX场景'）",
        MESSAGE_STRATEGY_SOFT_CHECK: "轻量提醒（如'您觉得怎么样？'）",
    }
    
    prompt_parts = []
    prompt_parts.append("## 商品信息：")
    prompt_parts.append(f"商品名称：{product_name}")
    if tags:
        prompt_parts.append(f"标签：{', '.join(tags)}")
    if color:
        prompt_parts.append(f"颜色：{color}")
    if scene:
        prompt_parts.append(f"场景：{scene}")
    prompt_parts.append("")
    
    prompt_parts.append("## 顾客行为：")
    prompt_parts.append(f"{behavior_context}")
    prompt_parts.append("**重要：主消息必须自然引用顾客行为，如'我看你最近看了几次...'或'刚刚浏览挺久...'**")
    prompt_parts.append("")
    
    prompt_parts.append("## 任务要求：")
    prompt_parts.append(f"请生成 {len(strategies)} 条导购私聊话术，每条使用不同策略：")
    for i, (strategy, strategy_desc) in enumerate(strategies, 1):
        strategy_hint = strategy_descriptions.get(strategy, "轻量建议")
        prompt_parts.append(f"{i}. {strategy_desc}：{strategy_hint}")
    prompt_parts.append("")
    prompt_parts.append("要求：")
    prompt_parts.append(f"1. 每条长度 ≤ {max_length} 个中文字符")
    prompt_parts.append("2. 第一条消息必须引用顾客行为（如'我看你最近看了几次...'）")
    prompt_parts.append("3. 每条消息必须包含行动建议关键词（尺码/脚感/场景/库存/优惠/试穿等）")
    prompt_parts.append("4. 策略必须不同，不能是同一策略的不同表述")
    prompt_parts.append("5. 语气自然、亲切，像朋友聊天")
    prompt_parts.append("6. 禁止使用营销词汇（太香了/必入/闭眼冲等）")
    prompt_parts.append("")
    prompt_parts.append("## 输出格式：")
    prompt_parts.append("每条消息单独一行，用换行分隔，例如：")
    prompt_parts.append("我看你最近看了几次，有什么顾虑吗？")
    prompt_parts.append("这款黑色运动鞋很舒适，您平时穿什么码？")
    prompt_parts.append("黑色运动鞋适合日常运动，您觉得怎么样？")
    prompt_parts.append("")
    prompt_parts.append("只输出话术内容，不要其他说明：")
    
    return "\n".join(prompt_parts)


def _parse_llm_message_pack_by_strategy(
    response: str,
    strategies: List[tuple],
    rotation_key: int,
) -> Dict[str, str]:
    """按策略解析 LLM 响应（V5.6.0+）。"""
    # 按行分割，过滤空行
    lines = [line.strip() for line in response.split("\n") if line.strip()]
    
    # 移除编号前缀
    cleaned_lines = []
    for line in lines:
        cleaned = line
        if cleaned.startswith(("1.", "2.", "3.", "第一条：", "第二条：", "第三条：")):
            cleaned = cleaned.split("：", 1)[-1].strip()
            if cleaned.startswith(("1.", "2.", "3.")):
                cleaned = cleaned.split(".", 1)[-1].strip()
        cleaned_lines.append(cleaned)
    
    # 按策略分配消息（简单启发式：按顺序分配）
    result = {}
    strategy_keys = [s[0] for s in strategies]
    
    for i, msg in enumerate(cleaned_lines[:len(strategies)]):
        if i < len(strategy_keys):
            result[strategy_keys[i]] = msg
    
    # 如果消息数量不足，使用轮换键选择
    if len(result) < len(strategies):
        for strategy, _ in strategies:
            if strategy not in result and cleaned_lines:
                idx = (rotation_key + len(result)) % len(cleaned_lines)
                result[strategy] = cleaned_lines[idx]
    
    return result


def _build_message_pack_prompt(
    product: Product,
    intent_level: str,
    intent_reason: str,
    recommended_action: str,
    behavior_summary: Optional[Dict] = None,
    max_length: int = 120,
) -> str:
    """构建生成多条消息的提示词。"""
    # 提取商品信息
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "") if attributes else ""
    scene = attributes.get("scene", "") if attributes else ""
    
    # 构建行为上下文
    behavior_context = ""
    if behavior_summary:
        visit_count = behavior_summary.get("visit_count", 0)
        if visit_count >= 2:
            behavior_context = f"（提示：用户已访问 {visit_count} 次，可以在话术中自然提及，如'我看你最近看了几次...'）"
    
    # 动作提示
    action_hints = {
        ACTION_ASK_SIZE: "询问尺码（如'您平时穿什么码？'）",
        ACTION_REASSURE_COMFORT: "强调舒适度（如'这款穿着很舒服'）",
        ACTION_MENTION_STOCK: "提醒库存（如'库存不多'）",
        ACTION_MENTION_PROMO: "提及优惠（如果有促销活动）",
        ACTION_SCENE_RECOMMENDATION: "场景推荐（如'适合XX场景'）",
        ACTION_SOFT_CHECK_IN: "轻量提醒（如'这款还不错'）",
    }
    action_hint = action_hints.get(recommended_action, "轻量建议")
    
    prompt_parts = []
    prompt_parts.append("## 商品信息：")
    prompt_parts.append(f"商品名称：{product_name}")
    if tags:
        prompt_parts.append(f"标签：{', '.join(tags)}")
    if color:
        prompt_parts.append(f"颜色：{color}")
    if scene:
        prompt_parts.append(f"场景：{scene}")
    prompt_parts.append("")
    
    prompt_parts.append("## 顾客意图：")
    prompt_parts.append(f"意图级别：{intent_level}")
    prompt_parts.append(f"判断原因：{intent_reason}")
    if behavior_context:
        prompt_parts.append(f"行为上下文：{behavior_context}")
    prompt_parts.append("")
    
    prompt_parts.append("## 任务要求：")
    prompt_parts.append("请生成 2~3 条导购私聊话术，要求：")
    prompt_parts.append(f"1. 每条长度 ≤ {max_length} 个中文字符")
    prompt_parts.append(f"2. 每条必须包含：{action_hint}")
    prompt_parts.append("3. 语气自然、亲切，像朋友聊天")
    prompt_parts.append("4. 禁止使用营销词汇（太香了/必入/闭眼冲等）")
    prompt_parts.append("5. 所有信息必须基于商品数据，不编造")
    prompt_parts.append("")
    prompt_parts.append("## 输出格式：")
    prompt_parts.append("每条消息单独一行，用换行分隔，例如：")
    prompt_parts.append("这款黑色运动鞋很舒适，您平时穿什么码？")
    prompt_parts.append("黑色运动鞋适合日常运动，您觉得怎么样？")
    prompt_parts.append("")
    prompt_parts.append("只输出话术内容，不要其他说明：")
    
    return "\n".join(prompt_parts)


def _parse_llm_message_pack(response: str, recommended_action: str) -> List[str]:
    """解析 LLM 响应，提取多条消息。"""
    # 按行分割，过滤空行
    lines = [line.strip() for line in response.split("\n") if line.strip()]
    
    # 过滤掉明显的非消息内容（如"消息1："、"第一条："等）
    messages = []
    for line in lines:
        # 移除编号前缀（如"1. "、"第一条："等）
        cleaned = line
        if cleaned.startswith(("1.", "2.", "3.", "第一条：", "第二条：", "第三条：")):
            cleaned = cleaned.split("：", 1)[-1].strip()
            if cleaned.startswith(("1.", "2.", "3.")):
                cleaned = cleaned.split(".", 1)[-1].strip()
        
        # 检查是否包含行动建议关键词
        action_keywords = {
            ACTION_ASK_SIZE: ["码", "尺码", "号"],
            ACTION_REASSURE_COMFORT: ["舒适", "舒服", "脚感"],
            ACTION_MENTION_STOCK: ["库存", "现货"],
            ACTION_MENTION_PROMO: ["优惠", "活动", "促销"],
            ACTION_SCENE_RECOMMENDATION: ["适合", "场景", "可以"],
            ACTION_SOFT_CHECK_IN: ["不错", "可以", "看看"],
        }
        
        keywords = action_keywords.get(recommended_action, [])
        if keywords and any(kw in cleaned for kw in keywords):
            messages.append(cleaned)
        elif not keywords:  # 如果没有特定关键词要求，接受所有消息
            messages.append(cleaned)
    
    # 如果解析失败，至少返回第一条消息
    if not messages and lines:
        messages.append(lines[0])
    
    return messages[:3]  # 最多 3 条


def _generate_fallback_message_pack(
    product: Product,
    intent_level: str,
    recommended_action: str,
    behavior_summary: Optional[Dict] = None,
    max_length: int = 120,
) -> List[MessageItem]:
    """使用规则模板生成消息包（至少 2 条）。"""
    # 生成 primary 消息
    primary_msg = generate_fallback_copy(
        product=product,
        intent_level=intent_level,
        max_length=max_length,
    )
    
    # 生成 alternative 消息（根据 recommended_action 调整）
    alternative_msg = _generate_alternative_message(
        product=product,
        intent_level=intent_level,
        recommended_action=recommended_action,
        behavior_summary=behavior_summary,
        max_length=max_length,
        primary_msg=primary_msg,
    )
    
    messages = [
        MessageItem(
            type="primary",
            strategy=_get_strategy_description(intent_level),
            message=primary_msg,
        ),
        MessageItem(
            type="alternative",
            strategy=_get_strategy_description(intent_level),
            message=alternative_msg,
        ),
    ]
    
    # 如果可能，生成第三条消息
    if intent_level in (INTENT_HIGH, INTENT_HESITATING):
        third_msg = _generate_third_message(
            product=product,
            intent_level=intent_level,
            recommended_action=recommended_action,
            max_length=max_length,
            existing_messages=[primary_msg, alternative_msg],
        )
        if third_msg:
            messages.append(
                MessageItem(
                    type="alternative",
                    strategy=_get_strategy_description(intent_level),
                    message=third_msg,
                )
            )
    
    return messages


def _generate_alternative_message(
    product: Product,
    intent_level: str,
    recommended_action: str,
    behavior_summary: Optional[Dict] = None,
    max_length: int = 120,
    primary_msg: str = "",
) -> str:
    """生成备选消息（与 primary 不同角度）。"""
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "")
    scene = attributes.get("scene", "")
    
    # 根据 recommended_action 生成
    if recommended_action == ACTION_ASK_SIZE:
        if color:
            base = f"{color}的{product_name}"
        else:
            base = product_name
        if len(base) + 8 <= max_length:
            return f"{base}，您平时穿什么码？"
        else:
            return f"{base[:max_length-8]}，您穿什么码？"
    
    elif recommended_action == ACTION_REASSURE_COMFORT:
        key_tags = [t for t in tags if t in ["舒适", "百搭"]]
        tag_str = key_tags[0] if key_tags else "不错"
        if color:
            base = f"{color}的{product_name}，{tag_str}"
        else:
            base = f"{product_name}，{tag_str}"
        if len(base) + 6 <= max_length:
            return f"{base}，穿着很舒服"
        else:
            return base[:max_length]
    
    elif recommended_action == ACTION_MENTION_STOCK:
        if color:
            base = f"{color}的{product_name}"
        else:
            base = product_name
        if len(base) + 6 <= max_length:
            return f"{base}，库存不多"
        else:
            return base[:max_length]
    
    elif recommended_action == ACTION_SCENE_RECOMMENDATION:
        if scene:
            if color:
                base = f"{color}的{product_name}，适合{scene}"
            else:
                base = f"{product_name}，适合{scene}"
            return base[:max_length]
        else:
            key_tags = [t for t in tags if t in ["百搭", "时尚"]]
            tag_str = key_tags[0] if key_tags else "不错"
            if color:
                base = f"{color}的{product_name}，{tag_str}"
            else:
                base = f"{product_name}，{tag_str}"
            return base[:max_length]
    
    else:  # ACTION_SOFT_CHECK_IN
        if color:
            base = f"{color}的{product_name}"
        else:
            base = product_name
        key_tags = [t for t in tags if t in ["舒适", "百搭"]]
        if key_tags and len(base) + len(key_tags[0]) + 2 <= max_length:
            return f"{base}，{key_tags[0]}"
        else:
            return base[:max_length]


def _generate_third_message(
    product: Product,
    intent_level: str,
    recommended_action: str,
    max_length: int = 120,
    existing_messages: List[str] = None,
) -> Optional[str]:
    """生成第三条消息（如果可能）。"""
    if not existing_messages:
        existing_messages = []
    
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "")
    
    # 尝试不同的角度
    if recommended_action == ACTION_ASK_SIZE:
        # 第三条：强调舒适度
        key_tags = [t for t in tags if t in ["舒适"]]
        if key_tags:
            if color:
                base = f"{color}的{product_name}，{key_tags[0]}"
            else:
                base = f"{product_name}，{key_tags[0]}"
            if len(base) + 4 <= max_length:
                return f"{base}，可以试试"
            else:
                return base[:max_length]
    
    elif recommended_action == ACTION_REASSURE_COMFORT:
        # 第三条：询问意见
        if color:
            base = f"{color}的{product_name}"
        else:
            base = product_name
        if len(base) + 6 <= max_length:
            return f"{base}，您觉得怎么样？"
        else:
            return base[:max_length]
    
    # 默认：轻量推荐
    key_tags = [t for t in tags if t in ["百搭", "时尚"]]
    tag_str = key_tags[0] if key_tags else "不错"
    if color:
        base = f"{color}的{product_name}，{tag_str}"
    else:
        base = f"{product_name}，{tag_str}"
    return base[:max_length]


def _get_strategy_description(intent_level: str) -> str:
    """获取策略描述。"""
    strategies = {
        INTENT_HIGH: "主动推进",
        INTENT_HESITATING: "消除顾虑",
        INTENT_MEDIUM: "场景化推荐",
        INTENT_LOW: "轻量提醒",
    }
    return strategies.get(intent_level, "场景化推荐")


async def build_suggestion_pack(context: AgentContext) -> SalesSuggestion:
    """
    构建导购可执行建议包。
    
    核心功能：
    1. 选择推荐动作（recommended_action）
    2. 构建时机解释（why_now）
    3. 计算置信度（confidence）
    4. 生成消息包（message_pack，2~3条）
    5. 构建发送建议（send_recommendation）
    
    Args:
        context: Agent context (must have product, intent_level, etc.)
    
    Returns:
        SalesSuggestion instance
    """
    logger.info("=" * 80)
    logger.info("[SUGGESTION] Building sales suggestion pack")
    logger.info(
        f"[SUGGESTION] Context: sku={context.sku}, "
        f"intent_level={context.intent_level}, "
        f"allowed={context.extra.get('allowed', False)}"
    )
    
    # 验证前提条件
    if not context.product:
        raise ValueError("Product is required in context")
    if not context.intent_level:
        raise ValueError("Intent level is required in context")
    
    # 获取必要信息
    intent_level = context.intent_level
    intent_reason = context.extra.get("intent_reason", "用户浏览了商品")
    behavior_summary = context.behavior_summary
    allowed = context.extra.get("allowed", False)
    
    # 1. 选择推荐动作
    recommended_action, action_explanation = choose_recommended_action(
        intent_level=intent_level,
        behavior_summary=behavior_summary,
        product=context.product,
    )
    logger.info(
        f"[SUGGESTION] ✓ Recommended action: {recommended_action} "
        f"({action_explanation})"
    )
    
    # 2. 构建时机解释
    why_now = build_why_now(
        intent_level=intent_level,
        intent_reason=intent_reason,
        behavior_summary=behavior_summary,
    )
    logger.info(f"[SUGGESTION] ✓ Why now: {why_now}")
    
    # 3. 计算置信度
    confidence = calculate_confidence(
        intent_level=intent_level,
        behavior_summary=behavior_summary,
    )
    logger.info(f"[SUGGESTION] ✓ Confidence: {confidence}")
    
    # 4. 生成消息包（V5.6.0+ - 策略多样、行为感知、确定性轮换）
    rotation_window = get_rotation_window()
    message_pack = await generate_message_pack(
        product=context.product,
        intent_level=intent_level,
        intent_reason=intent_reason,
        recommended_action=recommended_action,
        behavior_summary=behavior_summary,
        user_id=context.user_id,
        rotation_window=rotation_window,
    )
    logger.info(f"[SUGGESTION] ✓ Message pack: {len(message_pack)} messages (strategies: {[msg.strategy for msg in message_pack]})")
    
    # 5. 构建发送建议（V5.6.0+ - 包含 best_timing 和 next_step）
    send_recommendation = build_send_recommendation(
        intent_level=intent_level,
        confidence=confidence,
        allowed=allowed,
        recommended_action=recommended_action,
    )
    logger.info(
        f"[SUGGESTION] ✓ Send recommendation: suggested={send_recommendation.suggested}, "
        f"risk={send_recommendation.risk_level}"
    )
    
    # 6. 生成 Follow-up Playbook（V5.8.0+ - 仅 high 和 hesitating）
    followup_playbook = build_followup_playbook(
        intent_level=intent_level,
        recommended_action=recommended_action,
    )
    logger.info(f"[SUGGESTION] ✓ Follow-up playbook: {len(followup_playbook)} items")
    
    suggestion = SalesSuggestion(
        intent_level=intent_level,
        confidence=confidence,
        why_now=why_now,
        recommended_action=recommended_action,
        action_explanation=action_explanation,
        message_pack=message_pack,
        send_recommendation=send_recommendation,
        followup_playbook=followup_playbook,
    )
    
    logger.info("=" * 80)
    
    return suggestion


def build_followup_playbook(
    intent_level: str,
    recommended_action: str,
) -> List[FollowupPlaybookItem]:
    """
    构建 Follow-up Playbook（导购下一句 SOP，V5.8.0+）。
    
    业务规则：
    - 仅 high 和 hesitating intent 生成 playbook
    - 短小、可直接复制使用
    - 匹配 intent level
    
    Args:
        intent_level: Intent level
        recommended_action: Recommended action
    
    Returns:
        List of FollowupPlaybookItem
    """
    if intent_level not in (INTENT_HIGH, INTENT_HESITATING):
        return []  # 仅 high 和 hesitating 生成
    
    playbook = []
    
    if recommended_action == ACTION_ASK_SIZE:
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客说尺码不确定",
                reply="你平时这类鞋穿多少码？脚背高不高？我帮你更准一点～",
            ),
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～你如果在意脚感或搭配，我也可以给你更具体的建议～",
            ),
        ])
    elif recommended_action == ACTION_ASK_CONCERN_TYPE:
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客说尺码不确定",
                reply="你平时这类鞋穿多少码？脚背高不高？我帮你更准一点～",
            ),
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～你如果在意脚感或搭配，我也可以给你更具体的建议～",
            ),
            FollowupPlaybookItem(
                condition="顾客说担心脚感",
                reply="这款脚感不错，很多人反馈穿着舒服，你平时穿鞋在意这个吗？",
            ),
        ])
    elif recommended_action == ACTION_REASSURE_COMFORT:
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客说担心脚感",
                reply="这款脚感不错，很多人反馈穿着舒服，你平时穿鞋在意这个吗？",
            ),
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～你如果在意脚感或搭配，我也可以给你更具体的建议～",
            ),
        ])
    elif recommended_action == ACTION_SCENE_RELATE:
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～你如果在意脚感或搭配，我也可以给你更具体的建议～",
            ),
            FollowupPlaybookItem(
                condition="顾客问适合什么场景",
                reply="这款适合日常通勤，很多人上班穿，你平时穿得多吗？",
            ),
        ])
    elif recommended_action == ACTION_MENTION_STOCK:
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客问库存",
                reply="我帮你看看现在还有哪些码，你平时穿多少码？",
            ),
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～库存还有，你如果确定要我可以帮你留一下～",
            ),
        ])
    elif recommended_action == ACTION_MENTION_PROMO:
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客问优惠",
                reply="我帮你看看现在有没有可用的券或活动～",
            ),
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～你如果在意优惠，我也可以帮你看看有没有合适的活动～",
            ),
        ])
    else:  # ACTION_SOFT_CHECK_IN
        playbook.extend([
            FollowupPlaybookItem(
                condition="顾客说再看看",
                reply="好的不急～你如果后面想了解，我也可以帮你看看～",
            ),
        ])
    
    return playbook


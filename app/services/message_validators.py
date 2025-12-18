"""Message validators for safety and compliance checks (V5.6.0+).

核心职责：
- 禁止词汇检查
- 长度限制检查
- 跨 SKU 泄漏检查
- 行动建议关键词检查
- 策略多样性检查
- 对话式验证（V5.8.0+）：问句、不以商品名开头、弱化短语检查
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional, Tuple

from app.services.prompt_templates import FORBIDDEN_MARKETING_WORDS

logger = logging.getLogger(__name__)

# 行动建议关键词（必须包含至少一个）
ACTION_HINT_KEYWORDS = [
    "尺码",
    "码",
    "号",
    "脚感",
    "舒适",
    "舒服",
    "场景",
    "适合",
    "库存",
    "现货",
    "优惠",
    "活动",
    "促销",
    "试穿",
    "搭配",
    "可以",
    "怎么样",
    "觉得",
    "呢",
    "吗",
]

# 弱化短语（Primary 消息和 guide_chat 中禁止使用）
WEAK_PHRASES = [
    "可以看看",
    "您觉得呢",
    "了解一下",
    "可以了解",
    "看看",
    "了解一下",
    "推荐给你",
    "值得入手",
]

# 问句标记（Primary 消息和 guide_chat 必须包含）
QUESTION_MARKERS = [
    "？",
    "?",
    "吗",
    "呢",
    "什么",
    "多少",
    "如何",
    "怎样",
    "怎么样",
    "要不要",
    "会不会",
    "能不能",
    "可不可以",
]

# 邀请回复短语（guide_chat 必须包含问句或邀请短语）
INVITATION_PHRASES = [
    "吗",
    "要不要",
    "可以帮",
    "是否",
    "我帮你",
    "我可以",
    "给你",
    "～",
]


def validate_message(
    message: str,
    current_sku: str,
    max_length: int = 45,
    require_action_hint: bool = True,
    is_primary: bool = False,
    product_name: Optional[str] = None,
    recommended_action: Optional[str] = None,
) -> Tuple[bool, Optional[str]]:
    """
    验证单条消息（综合检查，V5.8.0+ 增强对话式验证）。
    
    业务规则：
    - 禁止词汇检查
    - 长度限制检查
    - 跨 SKU 泄漏检查
    - 行动建议关键词检查（可选）
    - Primary 消息特殊规则（V5.8.0+）：
      * 必须是问句
      * 不能以完整商品名开头
      * 不能包含弱化短语
      * 必须对齐 recommended_action
    
    Args:
        message: 消息内容
        current_sku: 当前商品 SKU
        max_length: 最大长度
        require_action_hint: 是否要求包含行动建议关键词
        is_primary: 是否是 Primary 消息（V5.8.0+）
        product_name: 商品名称（用于检查是否以商品名开头）
        recommended_action: 推荐动作（用于对齐检查）
    
    Returns:
        (is_valid, error_message)
    """
    # 1. 长度检查
    if len(message) > max_length:
        return False, f"消息长度 {len(message)} 超过限制 {max_length}"
    
    # 2. 非空检查
    if not message or not message.strip():
        return False, "消息为空"
    
    # 3. 禁止词汇检查
    for word in FORBIDDEN_MARKETING_WORDS:
        if word in message:
            return False, f"消息包含禁止的营销词汇：{word}"
    
    # 4. 跨 SKU 泄漏检查
    is_valid_sku, sku_error = validate_no_cross_sku_leakage(message, current_sku)
    if not is_valid_sku:
        return False, sku_error
    
    # 5. 行动建议关键词检查（可选）
    if require_action_hint:
        has_hint = any(keyword in message for keyword in ACTION_HINT_KEYWORDS)
        if not has_hint:
            return False, "消息缺少行动建议关键词"
    
    # 6. Primary 消息特殊规则（V5.8.0+）
    if is_primary:
        # 6.1 必须是问句
        has_question = any(marker in message for marker in QUESTION_MARKERS)
        if not has_question:
            return False, "Primary 消息必须是问句（包含'？'或疑问词）"
        
        # 6.2 不能以完整商品名开头
        if product_name and message.strip().startswith(product_name):
            return False, f"Primary 消息不能以完整商品名开头（应使用'这款'/'这双'等）"
        
        # 6.3 不能包含弱化短语
        for weak_phrase in WEAK_PHRASES:
            if weak_phrase in message:
                return False, f"Primary 消息不能包含弱化短语：{weak_phrase}"
        
        # 6.4 必须对齐 recommended_action
        if recommended_action:
            action_aligned = _check_action_alignment(message, recommended_action)
            if not action_aligned:
                return False, f"Primary 消息必须对齐 recommended_action={recommended_action}"
    
    return True, None


def validate_no_cross_sku_leakage(message: str, current_sku: str) -> Tuple[bool, Optional[str]]:
    """
    检查消息是否包含其他 SKU（跨 SKU 泄漏）。
    
    业务规则：
    - 如果消息包含 SKU 标记，必须只包含当前 SKU
    - 使用正则表达式检测 SKU 模式
    
    Args:
        message: 消息内容
        current_sku: 当前商品 SKU
    
    Returns:
        (is_valid, error_message)
    """
    # SKU 模式：\[SKU:XXX\] 或 SKU: XXX
    sku_pattern = re.compile(r'\[SKU:([^\]]+)\]|SKU:\s*([A-Z0-9]+)', re.IGNORECASE)
    
    matches = sku_pattern.findall(message)
    if not matches:
        # 没有 SKU 标记，通过
        return True, None
    
    # 检查所有匹配的 SKU
    for match in matches:
        found_sku = (match[0] or match[1]).upper()
        if found_sku != current_sku.upper():
            return False, f"消息包含其他商品的 SKU：{found_sku}（当前商品：{current_sku}）"
    
    return True, None


def validate_message_pack(
    message_pack: List[dict],
    current_sku: str,
    max_length: int = 45,
    min_count: int = 3,
) -> Tuple[bool, Optional[str]]:
    """
    验证消息包（综合检查）。
    
    业务规则：
    - 至少 min_count 条消息
    - 策略必须不同（无重复）
    - 备选消息不能是主消息的截断版本
    - 每条消息通过单条验证
    
    Args:
        message_pack: 消息包（List of dict with 'strategy' and 'message' keys）
        current_sku: 当前商品 SKU
        max_length: 最大长度
        min_count: 最小消息数量
    
    Returns:
        (is_valid, error_message)
    """
    # 1. 数量检查
    if len(message_pack) < min_count:
        return False, f"消息包数量 {len(message_pack)} 少于最小要求 {min_count}"
    
    # 2. 策略多样性检查
    strategies = [msg.get("strategy", "") for msg in message_pack]
    unique_strategies = set(strategies)
    if len(unique_strategies) < min_count:
        return False, f"消息包策略重复：{strategies}（需要至少 {min_count} 个不同策略）"
    
    # 3. 单条消息验证
    for i, msg in enumerate(message_pack):
        message = msg.get("message", "")
        is_valid, error = validate_message(
            message=message,
            current_sku=current_sku,
            max_length=max_length,
            require_action_hint=True,
        )
        if not is_valid:
            return False, f"消息 {i+1} 验证失败：{error}"
    
    # 4. 检查备选消息不是主消息的截断版本
    if len(message_pack) > 1:
        primary_message = message_pack[0].get("message", "")
        for i, msg in enumerate(message_pack[1:], 1):
            alt_message = msg.get("message", "")
            # 检查是否是截断版本（简单启发式：alt 是 primary 的子串）
            if alt_message in primary_message and len(alt_message) < len(primary_message) * 0.8:
                return False, f"备选消息 {i+1} 是主消息的截断版本"
    
    return True, None


def check_action_hint_presence(message: str) -> bool:
    """
    检查消息是否包含行动建议关键词。
    
    Args:
        message: 消息内容
    
    Returns:
        True if contains at least one action hint keyword
    """
    return any(keyword in message for keyword in ACTION_HINT_KEYWORDS)


def validate_guide_chat_message(
    message: str,
    current_sku: str,
    product_name: str,
    max_length: int = 50,
    min_length: int = 10,
) -> Tuple[bool, Optional[str]]:
    """
    专门验证 guide_chat 消息（V5.8.2+）。
    
    业务规则：
    - 不能以完整商品名开头（应使用"这款"/"这双"等）
    - 必须是问句或包含邀请回复短语
    - 必须包含行动建议关键词
    - 不能包含弱化短语
    - 长度限制：10-50 字符
    
    Args:
        message: 消息内容
        current_sku: 当前商品 SKU
        product_name: 商品名称
        max_length: 最大长度（默认 50）
        min_length: 最小长度（默认 10）
    
    Returns:
        (is_valid, error_message)
    """
    # 1. 长度检查
    if len(message) < min_length:
        return False, f"消息长度 {len(message)} 少于最小要求 {min_length}"
    if len(message) > max_length:
        return False, f"消息长度 {len(message)} 超过限制 {max_length}"
    
    # 2. 非空检查
    if not message or not message.strip():
        return False, "消息为空"
    
    # 3. 禁止词汇检查
    for word in FORBIDDEN_MARKETING_WORDS:
        if word in message:
            return False, f"消息包含禁止的营销词汇：{word}"
    
    # 4. 跨 SKU 泄漏检查
    is_valid_sku, sku_error = validate_no_cross_sku_leakage(message, current_sku)
    if not is_valid_sku:
        return False, sku_error
    
    # 5. 不能以完整商品名开头
    if message.strip().startswith(product_name):
        return False, f"guide_chat 消息不能以完整商品名开头（应使用'这款'/'这双'等）"
    
    # 6. 必须是问句或包含邀请回复短语
    has_question = any(marker in message for marker in QUESTION_MARKERS)
    has_invitation = any(phrase in message for phrase in INVITATION_PHRASES)
    if not (has_question or has_invitation):
        return False, "guide_chat 消息必须是问句或包含邀请回复短语（如'吗'/'要不要'/'可以帮'/'我帮你'等）"
    
    # 7. 必须包含行动建议关键词
    has_hint = any(keyword in message for keyword in ACTION_HINT_KEYWORDS)
    if not has_hint:
        return False, "guide_chat 消息必须包含行动建议关键词（尺码/脚感/场景/适合/库存/优惠等）"
    
    # 8. 不能包含弱化短语
    for weak_phrase in WEAK_PHRASES:
        if weak_phrase in message:
            return False, f"guide_chat 消息不能包含弱化短语：{weak_phrase}"
    
    return True, None


def _check_action_alignment(message: str, recommended_action: str) -> bool:
    """
    检查消息是否对齐 recommended_action。
    
    业务规则：
    - ask_size → 必须包含尺码相关关键词
    - ask_concern_type → 必须包含顾虑相关关键词
    - reassure_comfort → 必须包含舒适度相关关键词
    - scene_relate → 必须包含场景相关关键词
    - mention_stock → 必须包含库存相关关键词
    - mention_promo → 必须包含优惠相关关键词
    - soft_check_in → 轻量提醒（较宽松）
    
    Args:
        message: 消息内容
        recommended_action: 推荐动作
    
    Returns:
        True if aligned
    """
    action_keywords_map = {
        "ask_size": ["尺码", "码", "号", "穿多少码", "什么码"],
        "ask_concern_type": ["顾虑", "纠结", "担心", "疑问", "问题"],
        "reassure_comfort": ["舒适", "舒服", "脚感", "不用担心"],
        "scene_relate": ["场景", "适合", "穿", "用", "场合"],
        "mention_stock": ["库存", "现货", "还有", "剩"],
        "mention_promo": ["优惠", "活动", "券", "促销"],
        "soft_check_in": ["怎么样", "觉得", "呢", "吗"],  # 较宽松
    }
    
    keywords = action_keywords_map.get(recommended_action, [])
    if not keywords:
        return True  # 未知动作，不强制检查
    
    return any(keyword in message for keyword in keywords)


def validate_primary_message(
    message: str,
    current_sku: str,
    product_name: str,
    recommended_action: str,
    max_length: int = 45,
) -> Tuple[bool, Optional[str]]:
    """
    专门验证 Primary 消息（V5.8.0+）。
    
    业务规则：
    - 必须是问句
    - 不能以完整商品名开头
    - 不能包含弱化短语
    - 必须对齐 recommended_action
    - 必须包含行动建议关键词
    
    Args:
        message: 消息内容
        current_sku: 当前商品 SKU
        product_name: 商品名称
        recommended_action: 推荐动作
        max_length: 最大长度
    
    Returns:
        (is_valid, error_message)
    """
    return validate_message(
        message=message,
        current_sku=current_sku,
        max_length=max_length,
        require_action_hint=True,
        is_primary=True,
        product_name=product_name,
        recommended_action=recommended_action,
    )


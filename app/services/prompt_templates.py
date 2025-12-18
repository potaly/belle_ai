"""Prompt templates for private-chat sales copy generation.

重构说明：
- 将文案生成从"营销广告"升级为"导购 1v1 私聊促单话术"
- 语气自然、非营销
- 根据 intent_level 使用不同策略
- 包含轻量行动建议（尺码/场景/库存/促销/舒适度）
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from app.models.product import Product

logger = logging.getLogger(__name__)

# Intent levels
INTENT_HIGH = "high"
INTENT_MEDIUM = "medium"
INTENT_LOW = "low"
INTENT_HESITATING = "hesitating"

# 禁止使用的营销词汇
FORBIDDEN_MARKETING_WORDS = [
    "太香了",
    "必入",
    "闭眼冲",
    "爆款",
    "秒杀",
    "抢购",
    "限时",
    "仅此一次",
    "错过后悔",
    "史上最低",
    "血亏",
    "亏本",
    "清仓",
    "最后机会",
]


def build_system_prompt() -> str:
    """
    构建系统提示词（角色定义和约束）。
    
    核心要求：
    - 定义角色为真实门店导购
    - 禁止营销词汇
    - 严格事实约束（禁止幻觉）
    
    Returns:
        系统提示词字符串
    """
    return """你是一位真实门店的导购，正在通过微信与顾客进行 1 对 1 私聊。

## 角色要求：
1. **语气自然亲切**：像朋友聊天一样，不要像广告推销
2. **真实可信**：基于商品事实，不夸大不编造
3. **适度引导**：轻量建议，不强推不施压

## 严格禁止：
1. **禁止使用营销词汇**：如"太香了"、"必入"、"闭眼冲"、"爆款"、"秒杀"等
2. **禁止夸大宣传**：不编造商品没有的特点
3. **禁止强推**：不要使用"必须"、"一定要"等强制语气
4. **禁止编造事实**：所有信息必须来自提供的商品数据

## 输出要求：
1. 长度：≤ 45 个中文字符（可配置）
2. 语气：自然、亲切、日常
3. 必须包含：一个轻量行动建议（尺码/场景/库存/促销/舒适度等）
4. 格式：纯文本，不要表情符号，不要换行"""


def build_user_prompt(
    product: Product,
    intent_level: str,
    intent_reason: str,
    behavior_summary: Optional[Dict] = None,
    max_length: int = 45,
) -> str:
    """
    构建用户提示词（商品事实、行为摘要、意图级别、策略建议）。
    
    Args:
        product: 商品信息（唯一事实来源）
        intent_level: 意图级别（high/hesitating/medium/low）
        intent_reason: 意图判断原因
        behavior_summary: 行为摘要（可选）
        max_length: 最大长度（默认 45 字符）
    
    Returns:
        用户提示词字符串
    """
    # 提取商品信息（唯一事实来源）
    product_name = product.name
    tags = product.tags or []
    tags_str = "、".join(tags) if tags else ""
    attributes = product.attributes or {}
    color = attributes.get("color", "")
    scene = attributes.get("scene", "")
    material = attributes.get("material", "")
    price = product.price
    
    # 根据 intent_level 确定策略
    strategy = _get_strategy_by_intent(intent_level)
    
    # 构建提示词
    prompt_parts = []
    
    # 商品信息（唯一事实来源）
    prompt_parts.append("## 商品信息（唯一事实来源）：")
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
    prompt_parts.append("**重要：所有文案内容必须基于以上商品信息，禁止编造任何信息。**")
    prompt_parts.append("")
    
    # 顾客意图分析
    prompt_parts.append("## 顾客意图分析：")
    prompt_parts.append(f"意图级别：{intent_level}")
    prompt_parts.append(f"判断原因：{intent_reason}")
    if behavior_summary:
        visit_count = behavior_summary.get("visit_count", 0)
        avg_stay = behavior_summary.get("avg_stay_seconds", 0)
        has_favorite = behavior_summary.get("has_favorite", False)
        has_enter_buy_page = behavior_summary.get("has_enter_buy_page", False)
        
        behavior_info = []
        if visit_count > 0:
            behavior_info.append(f"访问 {visit_count} 次")
        if avg_stay > 0:
            behavior_info.append(f"平均停留 {avg_stay:.0f} 秒")
        if has_favorite:
            behavior_info.append("已收藏")
        if has_enter_buy_page:
            behavior_info.append("进入购买页")
        
        if behavior_info:
            prompt_parts.append(f"行为摘要：{', '.join(behavior_info)}")
    prompt_parts.append("")
    
    # 策略建议
    prompt_parts.append("## 话术策略：")
    prompt_parts.append(strategy)
    prompt_parts.append("")
    
    # 输出要求
    prompt_parts.append("## 输出要求：")
    prompt_parts.append(f"1. 长度：≤ {max_length} 个中文字符")
    prompt_parts.append("2. 语气：自然、亲切、像朋友聊天")
    prompt_parts.append("3. 必须包含：一个轻量行动建议（根据策略）")
    
    if intent_level == INTENT_LOW:
        prompt_parts.append("4. **重要**：语气要克制，不要强推，不要使用强烈的行动号召")
    else:
        prompt_parts.append("4. 适度引导，不强推不施压")
    
    prompt_parts.append("")
    prompt_parts.append("只输出话术内容，不要其他说明：")
    
    return "\n".join(prompt_parts)


def _get_strategy_by_intent(intent_level: str) -> str:
    """
    根据意图级别返回策略建议。
    
    Args:
        intent_level: 意图级别（high/hesitating/medium/low）
    
    Returns:
        策略建议字符串
    """
    strategies = {
        INTENT_HIGH: """顾客购买意图强烈，可以主动推进：
- 建议询问尺码（"您平时穿什么码？"）
- 提醒库存（"这款库存不多，建议尽快下单"）
- 提及促销（如果有优惠活动）
- 强调舒适度（"这款穿着很舒服，适合日常运动"）""",
        
        INTENT_HESITATING: """顾客处于犹豫状态，需要消除顾虑：
- 轻量提问（"您对这款有什么疑问吗？"）
- 场景推荐（"这款适合XX场景，您平时会用到吗？"）
- 舒适度保证（"这款材质很舒适，不用担心"）
- 避免强推，以询问为主""",
        
        INTENT_MEDIUM: """顾客有一定兴趣，可以场景化推荐：
- 场景建议（"这款适合XX场景，比如XX"）
- 搭配建议（"可以搭配XX，很百搭"）
- 轻量询问（"您平时会用到吗？"）""",
        
        INTENT_LOW: """顾客兴趣较低，保持克制：
- 轻量提醒（"这款商品还不错，您可以看看"）
- 不要强推，不要使用强烈的行动号召
- 语气要克制，避免施压""",
    }
    
    return strategies.get(intent_level, strategies[INTENT_MEDIUM])


def validate_copy_output(copy_text: str, max_length: int = 45) -> tuple[bool, Optional[str]]:
    """
    验证生成的文案是否符合要求。
    
    Args:
        copy_text: 生成的文案
        max_length: 最大长度
    
    Returns:
        (is_valid, error_message)
    """
    # 检查长度
    if len(copy_text) > max_length:
        return False, f"文案长度 {len(copy_text)} 超过限制 {max_length}"
    
    # 检查禁止词汇
    for word in FORBIDDEN_MARKETING_WORDS:
        if word in copy_text:
            return False, f"文案包含禁止的营销词汇：{word}"
    
    # 检查是否为空
    if not copy_text or not copy_text.strip():
        return False, "文案为空"
    
    return True, None


# ============================================================================
# Product-level copy generation prompts (V5.5.0+)
# ============================================================================


def build_product_copy_system_prompt() -> str:
    """
    构建商品话术生成的系统提示词。
    
    核心要求：
    - 定义角色为经验丰富的门店导购
    - 禁止夸大、禁止幻觉
    - 商品事实是唯一真相
    
    Returns:
        系统提示词字符串
    """
    return """你是一位经验丰富的门店导购，擅长用自然、亲切的语言介绍商品。

## 角色要求：
1. **真实可信**：基于商品事实，不夸大不编造
2. **自然亲切**：语气像朋友推荐，不要像广告推销
3. **实用导向**：突出商品的实际价值和使用场景

## 严格禁止：
1. **禁止使用营销词汇**：如"太香了"、"必入"、"闭眼冲"、"爆款"、"秒杀"、"神鞋"等
2. **禁止夸大宣传**：不编造商品没有的特点
3. **禁止编造事实**：所有信息必须来自提供的商品数据
4. **禁止引用其他商品**：只介绍当前商品，不提及其他 SKU

## 输出要求：
1. 语气：自然、亲切、日常
2. 长度：符合指定要求（默认 ≤ 50 字符）
3. 内容：基于商品卖点，突出实际价值"""


def build_product_copy_user_prompt(
    product: Product,
    selling_points: List[str],
    scene: str = "guide_chat",
    style: str = "natural",
    max_length: int = 50,
) -> str:
    """
    构建商品话术生成的用户提示词。
    
    Args:
        product: Product instance
        selling_points: List of selling points
        scene: Target scene (guide_chat / moments / poster)
        style: Writing style (natural / professional / friendly)
        max_length: Maximum length
    
    Returns:
        用户提示词字符串
    """
    # 提取商品信息
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    color = attributes.get("color", "") if attributes else ""
    material = attributes.get("material", "") if attributes else ""
    scene_attr = attributes.get("scene", "") if attributes else ""
    price = product.price
    
    # 场景描述（V5.8.2+ - guide_chat 特殊要求）
    scene_descriptions = {
        "guide_chat": "导购私聊场景（1对1对话式开场，必须能自然开启对话）",
        "moments": "朋友圈场景（适合分享，语气轻松）",
        "poster": "海报场景（简洁有力，突出卖点）",
    }
    scene_desc = scene_descriptions.get(scene, scene_descriptions["guide_chat"])
    
    # 风格描述
    style_descriptions = {
        "natural": "自然、亲切、日常",
        "professional": "专业、权威、可信",
        "friendly": "友好、热情、轻松",
    }
    style_desc = style_descriptions.get(style, style_descriptions["natural"])
    
    # 构建提示词
    prompt_parts = []
    
    # 商品信息（唯一事实来源）
    prompt_parts.append("## 商品信息（唯一事实来源）：")
    prompt_parts.append(f"商品名称：{product_name}")
    if color:
        prompt_parts.append(f"颜色：{color}")
    if material:
        prompt_parts.append(f"材质：{material}")
    if scene_attr:
        prompt_parts.append(f"适用场景：{scene_attr}")
    if tags:
        prompt_parts.append(f"标签：{', '.join(tags)}")
    if price:
        prompt_parts.append(f"价格：{price}元")
    prompt_parts.append("")
    prompt_parts.append("**重要：所有话术内容必须基于以上商品信息，禁止编造任何信息。**")
    prompt_parts.append("")
    
    # 商品卖点
    prompt_parts.append("## 商品卖点：")
    for i, point in enumerate(selling_points, 1):
        prompt_parts.append(f"{i}. {point}")
    prompt_parts.append("")
    
    # 任务要求（V5.8.2+ - guide_chat 特殊规则）
    prompt_parts.append("## 任务要求：")
    prompt_parts.append(f"请生成 2-3 条商品话术，用于{scene_desc}。")
    prompt_parts.append("")
    
    if scene == "guide_chat":
        # guide_chat 特殊要求（对话式骨架）
        prompt_parts.append("**重要：guide_chat 场景必须使用对话式骨架，像经验导购发的第一句话。**")
        prompt_parts.append("")
        prompt_parts.append("强制要求：")
        prompt_parts.append("1. **开头形式**（至少满足一个）：")
        prompt_parts.append("   - 使用'这款'/'这双'开头（不能以完整商品名开头）")
        prompt_parts.append("   - 使用'你平时...'开头")
        prompt_parts.append("   - 使用'如果你在意...'开头")
        prompt_parts.append("   - 使用'我可以帮你...'开头")
        prompt_parts.append("")
        prompt_parts.append("2. **必须是问句或包含邀请回复**：")
        prompt_parts.append("   - 必须包含'？'或疑问词（'吗'/'呢'/'什么'/'多少'等）")
        prompt_parts.append("   - 或包含邀请短语（'要不要'/'可以帮'/'我帮你'/'我可以'等）")
        prompt_parts.append("")
        prompt_parts.append("3. **必须包含行动建议关键词**：")
        prompt_parts.append("   - 尺码/码/号（询问尺码）")
        prompt_parts.append("   - 脚感/舒适/舒服（询问舒适度）")
        prompt_parts.append("   - 场景/适合/穿（询问使用场景）")
        prompt_parts.append("   - 搭配/库存/优惠等")
        prompt_parts.append("")
        prompt_parts.append("4. **严格禁止**：")
        prompt_parts.append("   - ❌ 不能以完整商品名开头（如'黑色的运动鞋女2024新款...'）")
        prompt_parts.append("   - ❌ 不能包含弱化短语：'可以看看'/'您觉得呢'/'了解一下'/'推荐给你'/'值得入手'")
        prompt_parts.append("   - ❌ 不能是纯描述性语句（必须有问句或邀请）")
        prompt_parts.append("")
        prompt_parts.append("5. **卖点使用规则**：")
        prompt_parts.append("   - 不要列举卖点（如'百搭、舒适、时尚，适合运动'）")
        prompt_parts.append("   - 自然嵌入卖点到对话中（如'这双偏百搭，平时通勤或运动穿都合适，你更常在哪种场景穿？'）")
        prompt_parts.append("")
        prompt_parts.append(f"6. 风格：{style_desc}")
        prompt_parts.append(f"7. 长度：{min(10, max_length // 5)}-{max_length} 个中文字符")
        prompt_parts.append("8. 禁止使用营销词汇（太香了/必入/爆款等）")
        prompt_parts.append("")
        prompt_parts.append("## 输出格式：")
        prompt_parts.append("每条话术单独一行，用换行分隔，例如：")
        prompt_parts.append("这双黑色挺百搭的，你平时通勤多还是运动多？我按场景给你推荐～")
        prompt_parts.append("这款脚感偏软，久走不累；你平时穿多少码？我帮你对一下～")
        prompt_parts.append("如果你比较在意脚感或搭配，我可以给你简单说下这双的特点～")
    else:
        # moments / poster 场景（保持原有要求）
        prompt_parts.append("要求：")
        prompt_parts.append(f"1. 风格：{style_desc}")
        prompt_parts.append(f"2. 长度：≤ {max_length} 个中文字符")
        prompt_parts.append("3. 基于商品卖点，突出实际价值")
        prompt_parts.append("4. 语气自然，不要像广告")
        prompt_parts.append("5. 禁止使用营销词汇（太香了/必入/爆款等）")
        prompt_parts.append("")
        prompt_parts.append("## 输出格式：")
        prompt_parts.append("每条话术单独一行，用换行分隔，例如：")
        prompt_parts.append("这款黑色运动鞋很舒适，适合日常运动")
        prompt_parts.append("黑色运动鞋，透气轻便，百搭实用")
    
    prompt_parts.append("")
    prompt_parts.append("只输出话术内容，不要其他说明：")
    
    return "\n".join(prompt_parts)


"""Validators for vision analysis output (V6.0.0+).

验证视觉分析输出的安全性和合规性。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

# 禁止输出的关键词（SKU/价格/优惠/库存/链接）
FORBIDDEN_KEYWORDS = [
    "SKU",
    "货号",
    "款号",
    "编码",
    "价格",
    "优惠",
    "促销",
    "库存",
    "现货",
    "链接",
    "网址",
    "http://",
    "https://",
    "www.",
    ".com",
    ".cn",
]

# 禁止编造的信息关键词（材质/功能）
FORBIDDEN_FABRICATION_KEYWORDS = [
    "真皮",
    "PU",
    "科技材料",
    "气垫",
    "防水",
    "保暖",
    "透气",
    "防滑",
    "缓震",
    "支撑",
    "科技",
    "技术",
]


def validate_vision_output(raw_result: Dict) -> Dict:
    """
    验证视觉分析输出。
    
    检查项：
    1. JSON 结构完整性
    2. 禁止关键词（SKU/价格/库存/链接）
    3. 禁止编造信息（材质/功能）
    
    Args:
        raw_result: 原始模型输出
    
    Returns:
        验证后的结果（如果验证失败，返回安全 fallback）
    
    Raises:
        ValueError: 当输出严重不符合要求时
    """
    logger.info("[VISION_VALIDATOR] Validating vision output...")

    # 1. 检查基本结构
    if not isinstance(raw_result, dict):
        logger.warning("[VISION_VALIDATOR] Output is not a dict, using fallback")
        return _get_fallback_result()

    # 2. 检查必需字段
    required_fields = ["visual_summary", "selling_points", "guide_chat_copy"]
    for field in required_fields:
        if field not in raw_result:
            logger.warning(f"[VISION_VALIDATOR] Missing required field: {field}, using fallback")
            return _get_fallback_result()

    # 3. 验证 guide_chat_copy
    guide_chat_copy = raw_result.get("guide_chat_copy", {})
    if not isinstance(guide_chat_copy, dict):
        logger.warning("[VISION_VALIDATOR] guide_chat_copy is not a dict, using fallback")
        return _get_fallback_result()

    primary = guide_chat_copy.get("primary", "")
    alternatives = guide_chat_copy.get("alternatives", [])

    # 4. 检查禁止关键词
    all_text = f"{primary} {' '.join(alternatives)} {' '.join(raw_result.get('selling_points', []))}"
    forbidden_found = _check_forbidden_keywords(all_text)
    if forbidden_found:
        logger.warning(
            f"[VISION_VALIDATOR] Found forbidden keywords: {forbidden_found}, using fallback"
        )
        return _get_fallback_result()

    # 5. 检查禁止编造信息（在 selling_points 中）
    selling_points = raw_result.get("selling_points", [])
    fabrication_found = _check_fabrication_keywords(selling_points)
    if fabrication_found:
        logger.warning(
            f"[VISION_VALIDATOR] Found fabrication keywords: {fabrication_found}, filtering..."
        )
        # 过滤掉包含编造信息的卖点
        raw_result["selling_points"] = [
            sp for sp in selling_points if not _contains_fabrication(sp)
        ]

    # 6. 检查 primary 是否包含提问
    if not _contains_question(primary):
        logger.warning(
            "[VISION_VALIDATOR] Primary message does not contain question, using fallback"
        )
        return _get_fallback_result()

    logger.info("[VISION_VALIDATOR] ✓ Output validated successfully")
    return raw_result


def _check_forbidden_keywords(text: str) -> List[str]:
    """检查禁止关键词。"""
    found = []
    text_lower = text.lower()
    for keyword in FORBIDDEN_KEYWORDS:
        if keyword.lower() in text_lower:
            found.append(keyword)
    return found


def _check_fabrication_keywords(selling_points: List[str]) -> List[str]:
    """检查禁止编造信息关键词。"""
    found = []
    for sp in selling_points:
        for keyword in FORBIDDEN_FABRICATION_KEYWORDS:
            if keyword in sp:
                found.append(keyword)
    return found


def _contains_fabrication(text: str) -> bool:
    """检查文本是否包含编造信息。"""
    for keyword in FORBIDDEN_FABRICATION_KEYWORDS:
        if keyword in text:
            return True
    return False


def _contains_question(text: str) -> bool:
    """检查文本是否包含提问（？或疑问词）。"""
    if "？" in text or "?" in text:
        return True
    question_words = ["吗", "呢", "还是", "多少", "什么", "怎么", "如何", "哪个"]
    for word in question_words:
        if word in text:
            return True
    return False


def _get_fallback_result() -> Dict:
    """获取安全 fallback 结果。"""
    return {
        "visual_summary": {
            "category_guess": "未知",
            "style_impression": ["日常"],
            "color_impression": "未知",
            "season_impression": "四季",
            "confidence_note": "基于图片外观判断，可能存在误差",
        },
        "selling_points": [
            "外观看起来比较百搭",
            "整体感觉偏轻便，适合日常穿",
        ],
        "guide_chat_copy": {
            "primary": "这双看起来不错，你平时穿什么码？",
            "alternatives": [
                "这款整体偏日常，穿着不会太累脚，你平时穿运动鞋多吗？",
                "这双风格比较休闲，搭牛仔裤也挺合适的",
                "从外观看感觉比较轻便，你平时更看重舒适度还是搭配？",
            ],
        },
        "confidence_level": "low",
    }


"""Vision feature normalizer (V6.0.0+).

将视觉分析结果归一化为可用于检索的结构化特征。
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 标准颜色集合（归一化目标）
STANDARD_COLORS = {
    "黑": "黑色",
    "白": "白色",
    "灰": "灰色",
    "棕": "棕色",
    "红": "红色",
    "蓝": "蓝色",
    "绿": "绿色",
    "黄": "黄色",
    "紫": "紫色",
    "粉": "粉色",
    "米": "米色",
    "驼": "驼色",
    "银": "银色",
    "金": "金色",
    "橙": "橙色",
    "卡其": "卡其色",
    "军绿": "军绿色",
    "藏青": "藏青色",
    "酒红": "酒红色",
    "咖啡": "咖啡色",
}

# 季节枚举
SEASON_ENUM = ["春夏", "秋冬", "四季", "不确定"]

# 类目同义词映射（简化版，实际可扩展）
CATEGORY_SYNONYMS = {
    "运动鞋": ["运动鞋", "跑鞋", "训练鞋", "健身鞋"],
    "休闲鞋": ["休闲鞋", "板鞋", "帆布鞋", "平底鞋"],
    "皮鞋": ["皮鞋", "正装鞋", "商务鞋"],
    "靴子": ["靴子", "短靴", "长靴", "马丁靴"],
    "凉鞋": ["凉鞋", "拖鞋", "沙滩鞋"],
    "高跟鞋": ["高跟鞋", "高跟", "细跟鞋"],
}


class VisionFeatureNormalizer:
    """视觉特征归一化器。"""

    @staticmethod
    def normalize(
        visual_summary: Dict,
        selling_points: List[str],
        brand_code: Optional[str] = None,
        scene: str = "guide_chat",
        category_resolver=None,
    ) -> Dict:
        """
        归一化视觉特征。
        
        Args:
            visual_summary: 视觉摘要（包含 category_guess, style_impression, color_impression, season_impression）
            selling_points: 卖点列表
            brand_code: 品牌编码（用于类目池约束，可选）
            scene: 使用场景（默认 guide_chat）
        
        Returns:
            归一化后的 vision_features 字典：
            {
                "category": "运动鞋",
                "style": ["休闲", "日常"],
                "color": "黑色",
                "colors": ["黑色", "白色"],
                "season": "四季",
                "scene": "guide_chat",
                "keywords": ["百搭", "轻便"]
            }
        """
        logger.info("[NORMALIZER] Normalizing vision features...")

        # 提取 keywords（用于辅助 category 匹配）
        keywords = VisionFeatureNormalizer._extract_keywords(visual_summary, selling_points)

        # 1. Category 归一化（使用 Category Resolver）
        category = VisionFeatureNormalizer._normalize_category(
            visual_summary.get("category_guess", ""),
            brand_code,
            category_resolver=category_resolver,
            keywords=keywords,
        )

        # 2. Color/Colors 归一化
        color_impression = visual_summary.get("color_impression", "")
        colors = VisionFeatureNormalizer._normalize_colors(color_impression)
        color = colors[0] if colors else None

        # 3. Style 归一化
        style_impression = visual_summary.get("style_impression", [])
        style = VisionFeatureNormalizer._normalize_style(style_impression)

        # 4. Season 归一化（如果提供了 category_resolver，使用其 resolve_season 方法）
        season_impression = visual_summary.get("season_impression", "")
        if category_resolver:
            try:
                season = category_resolver.resolve_season(season_impression)
            except Exception as e:
                logger.warning(f"[NORMALIZER] Category Resolver season resolution failed: {e}, using fallback")
                season = VisionFeatureNormalizer._normalize_season(season_impression)
        else:
            season = VisionFeatureNormalizer._normalize_season(season_impression)

        # Keywords 已在步骤1之前提取，直接使用

        result = {
            "category": category,
            "style": style,
            "color": color,
            "colors": colors,
            "season": season,
            "scene": scene,
            "keywords": keywords,
        }

        logger.info(f"[NORMALIZER] ✓ Normalized features: {result}")
        return result

    @staticmethod
    def _normalize_category(
        category_guess: str,
        brand_code: Optional[str] = None,
        category_resolver=None,
        keywords: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        归一化类目。
        
        规则：
        1. 如果 brand_code 存在且 category_resolver 可用，使用 Category Resolver 映射到 allowed_categories
        2. 否则使用同义词映射（向后兼容）
        3. 无法映射则置空
        
        Args:
            category_guess: Vision 模型输出的原始 category
            brand_code: 品牌编码
            category_resolver: CategoryResolver 实例（可选）
            keywords: 关键词列表（可选，用于辅助匹配）
        """
        if not category_guess or not category_guess.strip():
            return None

        category_guess = category_guess.strip()

        # 优先使用 Category Resolver（如果提供）
        if brand_code and category_resolver:
            try:
                resolved = category_resolver.resolve_category(
                    category_guess_raw=category_guess,
                    brand_code=brand_code,
                    keywords=keywords,
                )
                if resolved:
                    return resolved
            except Exception as e:
                logger.warning(
                    f"[NORMALIZER] Category Resolver failed: {e}, falling back to synonym mapping"
                )

        # 降级到同义词映射（向后兼容）
        for standard_category, synonyms in CATEGORY_SYNONYMS.items():
            if category_guess == standard_category:
                return standard_category
            for synonym in synonyms:
                if synonym in category_guess or category_guess in synonym:
                    return standard_category

        # 如果无法映射，返回 None（避免乱给）
        logger.warning(f"[NORMALIZER] Category '{category_guess}' cannot be normalized, returning None")
        return None

    @staticmethod
    def _normalize_colors(color_impression: str) -> List[str]:
        """
        归一化颜色。
        
        规则：
        1. 从 color_impression 中提取颜色词
        2. 映射到标准颜色集合
        3. 去重并返回列表
        """
        if not color_impression or not color_impression.strip():
            return []

        color_impression = color_impression.strip()
        colors = []

        # 提取颜色词（支持多种格式：黑色、黑、黑白色、黑/白等）
        # 先尝试直接匹配标准颜色
        for key, standard_color in STANDARD_COLORS.items():
            if key in color_impression or standard_color in color_impression:
                if standard_color not in colors:
                    colors.append(standard_color)

        # 如果没匹配到，尝试提取单个颜色字
        if not colors:
            for key, standard_color in STANDARD_COLORS.items():
                if key in color_impression:
                    if standard_color not in colors:
                        colors.append(standard_color)

        # 如果还是没匹配到，尝试从文本中提取（简单规则）
        if not colors:
            # 提取常见颜色词
            color_patterns = [
                r"([黑白灰棕红蓝绿黄紫粉米驼银金橙]色?)",
                r"(卡其|军绿|藏青|酒红|咖啡)",
            ]
            for pattern in color_patterns:
                matches = re.findall(pattern, color_impression)
                for match in matches:
                    # 映射到标准颜色
                    for key, standard_color in STANDARD_COLORS.items():
                        if key in match:
                            if standard_color not in colors:
                                colors.append(standard_color)
                            break

        logger.debug(f"[NORMALIZER] Normalized colors: {color_impression} -> {colors}")
        return colors

    @staticmethod
    def _normalize_style(style_impression: List[str]) -> List[str]:
        """
        归一化风格。
        
        规则：
        1. 去重
        2. 排序
        3. 最多保留 5 个
        """
        if not style_impression:
            return []

        # 去重并过滤空值
        style_set = set()
        for s in style_impression:
            if s and isinstance(s, str) and s.strip():
                style_set.add(s.strip())

        # 排序并限制数量
        style_list = sorted(list(style_set))[:5]

        logger.debug(f"[NORMALIZER] Normalized style: {style_impression} -> {style_list}")
        return style_list

    @staticmethod
    def _normalize_season(season_impression: str) -> str:
        """
        归一化季节。
        
        规则：
        1. 映射到枚举：春夏 / 秋冬 / 四季 / 不确定
        2. 默认返回 "四季"
        """
        if not season_impression or not season_impression.strip():
            return "四季"

        season_impression = season_impression.strip()

        # 精确匹配
        if season_impression in SEASON_ENUM:
            return season_impression

        # 模糊匹配
        if "春夏" in season_impression:
            return "春夏"
        if "秋冬" in season_impression:
            return "秋冬"
        if "四季" in season_impression or "全年" in season_impression:
            return "四季"

        # 默认返回 "四季"
        logger.debug(f"[NORMALIZER] Season '{season_impression}' not matched, using default '四季'")
        return "四季"

    @staticmethod
    def _extract_keywords(
        visual_summary: Dict, selling_points: List[str]
    ) -> List[str]:
        """
        提取关键词。
        
        规则：
        1. 从 selling_points 中提取 3~6 个短词
        2. 从 visual_summary 中提取补充关键词
        3. 过滤常见停用词
        """
        keywords = set()

        # 从 selling_points 提取
        for point in selling_points:
            if not point or not isinstance(point, str):
                continue
            # 提取短词（2-4个字符）
            words = re.findall(r"[\u4e00-\u9fa5]{2,4}", point)
            for word in words:
                if len(word) >= 2 and len(word) <= 4:
                    keywords.add(word)
                if len(keywords) >= 6:
                    break
            if len(keywords) >= 6:
                break

        # 从 visual_summary 提取补充关键词
        category_guess = visual_summary.get("category_guess", "")
        style_impression = visual_summary.get("style_impression", [])
        color_impression = visual_summary.get("color_impression", "")

        # 从 category_guess 提取
        if category_guess:
            words = re.findall(r"[\u4e00-\u9fa5]{2,4}", category_guess)
            for word in words:
                if len(word) >= 2 and len(word) <= 4:
                    keywords.add(word)

        # 从 style_impression 提取
        for style in style_impression:
            if style and isinstance(style, str) and len(style) >= 2:
                keywords.add(style)

        # 过滤停用词
        stop_words = {"的", "了", "是", "在", "有", "和", "与", "或", "及", "等", "这个", "那个"}
        keywords = {kw for kw in keywords if kw not in stop_words}

        # 限制数量并排序
        keywords_list = sorted(list(keywords))[:6]

        # 确保至少3个（如果不足，补充通用词）
        if len(keywords_list) < 3:
            fallback_keywords = ["百搭", "舒适", "时尚", "经典", "实用"]
            for fk in fallback_keywords:
                if fk not in keywords_list:
                    keywords_list.append(fk)
                if len(keywords_list) >= 3:
                    break

        logger.debug(f"[NORMALIZER] Extracted keywords: {keywords_list}")
        return keywords_list[:6]


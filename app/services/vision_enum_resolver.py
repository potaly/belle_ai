"""Vision enum resolver with fallback rules (P4.x.1).

实现规则兜底逻辑，确保输出符合品牌枚举约束。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class VisionEnumResolver:
    """Vision 枚举解析器（带规则兜底）。"""

    @staticmethod
    def resolve_with_fallback(
        vlm_output: Dict,
        allowed_enums: Dict[str, List[str]],
        brand_no: str,
    ) -> tuple[Dict, List[str]]:
        """
        解析 VLM 输出并应用规则兜底。
        
        Args:
            vlm_output: VLM 原始输出（JSON 解析后）
            allowed_enums: 允许的枚举值字典
            brand_no: 品牌编码
        
        Returns:
            Tuple of (resolved_output, corrections)
            - resolved_output: 修正后的输出
            - corrections: 修正记录列表
        """
        corrections = []
        resolved = vlm_output.copy()

        allowed_categories = allowed_enums.get("categories", [])
        allowed_seasons = allowed_enums.get("seasons", [])
        allowed_styles = allowed_enums.get("styles", [])
        allowed_colors = allowed_enums.get("colors", [])

        # 保存原始值（用于 debug）
        resolved["category_guess_raw"] = resolved.get("category", "")
        resolved["season_impression_raw"] = resolved.get("season", "")
        resolved["style_impression_raw"] = resolved.get("style", [])
        resolved["color_impression_raw"] = resolved.get("color", "")

        # 1. Category 兜底
        category_raw = resolved.get("category", "")
        category_final = category_raw

        # 规则1: 检查 category 是否在 allowed_categories 中
        if category_raw and category_raw not in allowed_categories:
            # 规则2: 根据 structure_signals 强制修正
            structure_signals = resolved.get("structure_signals", {})
            open_heel = structure_signals.get("open_heel", False)
            open_toe = structure_signals.get("open_toe", False)

            if open_heel and "后空凉鞋" in allowed_categories:
                category_final = "后空凉鞋"
                corrections.append(f"open_heel=>后空凉鞋")
            elif open_toe and "纯凉鞋" in allowed_categories:
                category_final = "纯凉鞋"
                corrections.append(f"open_toe=>纯凉鞋")
            else:
                # 无法修正，设为 UNKNOWN（如果允许）或第一个 allowed category
                if "UNKNOWN" in allowed_categories:
                    category_final = "UNKNOWN"
                    corrections.append(f"category_not_allowed=>UNKNOWN")
                elif allowed_categories:
                    category_final = allowed_categories[0]
                    corrections.append(f"category_not_allowed=>{category_final}")
                else:
                    category_final = None
                    corrections.append(f"category_not_allowed=>None (no allowed categories)")

        resolved["category"] = category_final
        resolved["category_guess"] = category_final

        # 2. Season 兜底
        season_raw = resolved.get("season", "")
        season_final = season_raw

        if season_raw and season_raw not in allowed_seasons:
            # 规则3: 根据 category 推断 season
            if category_final in {"后空凉鞋", "中空凉鞋", "纯凉鞋", "拖鞋"}:
                if "夏季" in allowed_seasons:
                    season_final = "夏季"
                    corrections.append(f"category_infers_season=>夏季")
                elif allowed_seasons:
                    season_final = allowed_seasons[0]
                    corrections.append(f"season_not_allowed=>{season_final}")
            elif allowed_seasons:
                season_final = allowed_seasons[0]
                corrections.append(f"season_not_allowed=>{season_final}")
            else:
                season_final = None
                corrections.append(f"season_not_allowed=>None (no allowed seasons)")

        resolved["season"] = season_final
        resolved["season_impression"] = season_final

        # 3. Style 兜底
        style_raw = resolved.get("style", [])
        if not isinstance(style_raw, list):
            style_raw = []

        style_final = []
        for style_item in style_raw[:3]:  # 最多3个
            if style_item in allowed_styles:
                style_final.append(style_item)
            elif allowed_styles:
                # 如果不在 allowed 中，尝试模糊匹配
                matched = False
                for allowed_style in allowed_styles:
                    if style_item in allowed_style or allowed_style in style_item:
                        style_final.append(allowed_style)
                        matched = True
                        break
                if not matched:
                    corrections.append(f"style_not_allowed=>{style_item} (skipped)")

        resolved["style"] = style_final
        resolved["style_impression"] = style_final

        # 4. Color 兜底
        color_raw = resolved.get("color", "")
        color_final = color_raw

        if color_raw and color_raw not in allowed_colors:
            # 尝试模糊匹配
            matched = False
            for allowed_color in allowed_colors:
                if color_raw in allowed_color or allowed_color in color_raw:
                    color_final = allowed_color
                    matched = True
                    break
            if not matched and allowed_colors:
                color_final = allowed_colors[0]
                corrections.append(f"color_not_allowed=>{color_final}")
            elif not matched:
                color_final = None
                corrections.append(f"color_not_allowed=>None (no allowed colors)")

        resolved["color"] = color_final
        resolved["color_impression"] = color_final

        # 5. Colors 数组兜底
        colors_raw = resolved.get("colors", [])
        if not isinstance(colors_raw, list):
            colors_raw = [color_final] if color_final else []

        colors_final = []
        for color_item in colors_raw[:2]:  # 最多2个
            if color_item in allowed_colors:
                colors_final.append(color_item)
            elif allowed_colors:
                # 模糊匹配
                for allowed_color in allowed_colors:
                    if color_item in allowed_color or allowed_color in color_item:
                        colors_final.append(allowed_color)
                        break

        if not colors_final and color_final:
            colors_final = [color_final]

        resolved["colors"] = colors_final

        logger.info(
            f"[ENUM_RESOLVER] Resolved for brand_no={brand_no}: "
            f"category={category_final}, season={season_final}, "
            f"corrections={corrections}"
        )

        return resolved, corrections


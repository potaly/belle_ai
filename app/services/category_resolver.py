"""Category Resolver (P4.x).

解决 Vision 识别出的 category/season 与业务枚举不一致导致的召回不准问题。

核心能力：
1. 从 products_staging 表查询品牌的 allowed_categories
2. 将 vision_analyze 的原始输出映射到 allowed_categories
3. 支持模糊匹配和相似度算法
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set
from difflib import SequenceMatcher

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# 季节枚举（业务标准）
SEASON_ENUM = ["春夏", "秋冬", "四季", "不确定"]


class CategoryResolver:
    """类目归一化解析器。"""

    def __init__(self, db: Session):
        """
        初始化 Category Resolver。
        
        Args:
            db: Database session
        """
        self.db = db
        self._category_cache: Dict[str, List[str]] = {}  # brand_code -> allowed_categories

    def get_allowed_categories(self, brand_code: str, use_cache: bool = True) -> List[str]:
        """
        获取品牌的 allowed_categories（从 products_staging 表查询）。
        
        Args:
            brand_code: 品牌编码（对应 products_staging.style_brand_no）
            use_cache: 是否使用缓存（默认 True）
        
        Returns:
            该品牌的所有 category 列表（去重、排序）
        """
        # 检查缓存
        if use_cache and brand_code in self._category_cache:
            logger.debug(f"[CATEGORY_RESOLVER] Using cached categories for brand_code={brand_code}")
            return self._category_cache[brand_code]

        logger.info(f"[CATEGORY_RESOLVER] Querying allowed categories for brand_code={brand_code}")

        try:
            # 查询 products_staging 表
            sql = """
            SELECT DISTINCT category
            FROM products_staging
            WHERE style_brand_no = :brand_code
              AND category IS NOT NULL
              AND category != ''
            ORDER BY category
            """
            result = self.db.execute(text(sql), {"brand_code": brand_code})
            categories = [row[0] for row in result if row[0]]

            logger.info(
                f"[CATEGORY_RESOLVER] ✓ Found {len(categories)} allowed categories for brand_code={brand_code}"
            )
            if categories:
                logger.debug(f"[CATEGORY_RESOLVER] Sample categories: {categories[:5]}")

            # 缓存结果
            if use_cache:
                self._category_cache[brand_code] = categories

            return categories

        except Exception as e:
            logger.error(
                f"[CATEGORY_RESOLVER] ✗ Failed to query allowed categories: {e}",
                exc_info=True,
            )
            return []

    def resolve_category(
        self,
        category_guess_raw: str,
        brand_code: str,
        keywords: Optional[List[str]] = None,
    ) -> Optional[str]:
        """
        将 vision_analyze 的原始 category_guess 映射到品牌的 allowed_categories。
        
        匹配策略（优先级从高到低）：
        1. 精确匹配（忽略大小写和空格）
        2. 包含匹配（category_guess 包含在 allowed_category 中，或相反）
        3. 相似度匹配（使用 SequenceMatcher，阈值 >= 0.6）
        4. 关键词匹配（如果 keywords 提供，检查是否包含 category 关键词）
        
        Args:
            category_guess_raw: Vision 模型输出的原始 category（如"单鞋"）
            brand_code: 品牌编码
            keywords: 关键词列表（可选，用于辅助匹配）
        
        Returns:
            映射后的 category（属于 allowed_categories），如果无法映射返回 None
        """
        if not category_guess_raw or not category_guess_raw.strip():
            logger.debug("[CATEGORY_RESOLVER] category_guess_raw is empty")
            return None

        category_guess = category_guess_raw.strip()
        logger.info(
            f"[CATEGORY_RESOLVER] Resolving category: '{category_guess}' for brand_code={brand_code}"
        )

        # 获取 allowed_categories
        allowed_categories = self.get_allowed_categories(brand_code)
        if not allowed_categories:
            logger.warning(
                f"[CATEGORY_RESOLVER] No allowed categories found for brand_code={brand_code}, "
                f"cannot resolve category"
            )
            return None

        # 策略1: 精确匹配（忽略大小写和空格）
        category_guess_normalized = category_guess.lower().replace(" ", "").replace("　", "")
        for allowed_cat in allowed_categories:
            allowed_cat_normalized = allowed_cat.lower().replace(" ", "").replace("　", "")
            if category_guess_normalized == allowed_cat_normalized:
                logger.info(
                    f"[CATEGORY_RESOLVER] ✓ Exact match: '{category_guess}' -> '{allowed_cat}'"
                )
                return allowed_cat

        # 策略2: 包含匹配
        for allowed_cat in allowed_categories:
            if category_guess in allowed_cat or allowed_cat in category_guess:
                logger.info(
                    f"[CATEGORY_RESOLVER] ✓ Contains match: '{category_guess}' -> '{allowed_cat}'"
                )
                return allowed_cat

        # 策略3: 相似度匹配（使用 SequenceMatcher）
        best_match = None
        best_score = 0.0
        threshold = 0.6

        for allowed_cat in allowed_categories:
            score = SequenceMatcher(None, category_guess, allowed_cat).ratio()
            if score > best_score:
                best_score = score
                best_match = allowed_cat

        if best_score >= threshold:
            logger.info(
                f"[CATEGORY_RESOLVER] ✓ Similarity match: '{category_guess}' -> '{best_match}' "
                f"(score={best_score:.2f})"
            )
            return best_match

        # 策略4: 关键词匹配（如果提供 keywords）
        if keywords:
            keywords_set = {kw.lower() for kw in keywords if kw}
            for allowed_cat in allowed_categories:
                # 检查 allowed_cat 是否包含 keywords 中的词
                allowed_cat_words = set(allowed_cat.lower().split())
                if keywords_set & allowed_cat_words:
                    logger.info(
                        f"[CATEGORY_RESOLVER] ✓ Keyword match: '{category_guess}' -> '{allowed_cat}' "
                        f"(keywords={keywords_set & allowed_cat_words})"
                    )
                    return allowed_cat

        # 无法匹配
        logger.warning(
            f"[CATEGORY_RESOLVER] ✗ Cannot resolve category: '{category_guess}' "
            f"(allowed_categories={allowed_categories[:5]}...)"
        )
        return None

    def resolve_season(self, season_raw: str) -> str:
        """
        归一化季节。
        
        规则：
        1. 映射到标准枚举：春夏 / 秋冬 / 四季 / 不确定
        2. 默认返回 "四季"
        
        Args:
            season_raw: Vision 模型输出的原始 season
        
        Returns:
            归一化后的 season（属于 SEASON_ENUM）
        """
        if not season_raw or not season_raw.strip():
            return "四季"

        season_raw = season_raw.strip()
        logger.debug(f"[CATEGORY_RESOLVER] Resolving season: '{season_raw}'")

        # 精确匹配
        if season_raw in SEASON_ENUM:
            return season_raw

        # 模糊匹配
        season_lower = season_raw.lower()
        if "春夏" in season_raw or "春" in season_raw or "夏" in season_raw:
            return "春夏"
        if "秋冬" in season_raw or ("秋" in season_raw and "冬" in season_raw):
            return "秋冬"
        if "四季" in season_raw or "全年" in season_raw or "通用" in season_raw:
            return "四季"

        # 默认返回 "四季"
        logger.debug(f"[CATEGORY_RESOLVER] Season '{season_raw}' not matched, using default '四季'")
        return "四季"

    def clear_cache(self, brand_code: Optional[str] = None) -> None:
        """
        清除缓存。
        
        Args:
            brand_code: 如果提供，只清除该品牌的缓存；否则清除所有缓存
        """
        if brand_code:
            self._category_cache.pop(brand_code, None)
            logger.debug(f"[CATEGORY_RESOLVER] Cleared cache for brand_code={brand_code}")
        else:
            self._category_cache.clear()
            logger.debug("[CATEGORY_RESOLVER] Cleared all cache")


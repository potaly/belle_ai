"""Brand vocabulary service (P4.x.1).

提供按 brand_no 获取 allowed enums 的方法，带缓存（TTL 10min）。
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

import redis
from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

# 缓存 TTL（秒）
CACHE_TTL_SECONDS = 600  # 10分钟


class BrandVocabService:
    """品牌词汇表服务（枚举约束）。"""

    def __init__(self, db: Session):
        """
        初始化 Brand Vocab Service。
        
        Args:
            db: Database session
        """
        self.db = db
        self._memory_cache: Dict[str, tuple[List[str], datetime]] = {}  # key -> (value, expires_at)

    def get_allowed_categories(self, brand_no: str, use_cache: bool = True) -> List[str]:
        """
        获取品牌的 allowed categories。
        
        Args:
            brand_no: 品牌编码
            use_cache: 是否使用缓存
        
        Returns:
            cat_name 列表（where is_active=1）
        """
        cache_key = f"vocab:{brand_no}:categories"
        
        # 检查内存缓存
        if use_cache and cache_key in self._memory_cache:
            value, expires_at = self._memory_cache[cache_key]
            if datetime.now() < expires_at:
                logger.debug(f"[BRAND_VOCAB] Using memory cache for {cache_key}")
                return value
            else:
                # 缓存过期，删除
                del self._memory_cache[cache_key]

        # 检查 Redis 缓存
        redis_client = None
        try:
            if settings.redis_url:
                redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                redis_client.ping()
        except Exception:
            redis_client = None

        if use_cache and redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    import json
                    categories = json.loads(cached)
                    logger.debug(f"[BRAND_VOCAB] Using Redis cache for {cache_key}")
                    # 更新内存缓存
                    self._memory_cache[cache_key] = (
                        categories,
                        datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS),
                    )
                    return categories
            except Exception as e:
                logger.warning(f"[BRAND_VOCAB] Redis cache read failed: {e}")

        # 从数据库查询
        logger.info(f"[BRAND_VOCAB] Querying allowed categories for brand_no={brand_no}")
        try:
            sql = """
            SELECT DISTINCT cat_name
            FROM product_categories
            WHERE brand_no = :brand_no
              AND is_active = 1
              AND cat_name IS NOT NULL
              AND cat_name != ''
            ORDER BY cat_name
            """
            result = self.db.execute(text(sql), {"brand_no": brand_no})
            categories = [row[0] for row in result if row[0]]

            logger.info(
                f"[BRAND_VOCAB] ✓ Found {len(categories)} allowed categories for brand_no={brand_no}"
            )
            if categories:
                logger.debug(f"[BRAND_VOCAB] Sample categories: {categories[:5]}")

            # 更新缓存
            expires_at = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
            self._memory_cache[cache_key] = (categories, expires_at)

            if redis_client:
                try:
                    import json
                    redis_client.setex(
                        cache_key,
                        CACHE_TTL_SECONDS,
                        json.dumps(categories, ensure_ascii=False),
                    )
                except Exception as e:
                    logger.warning(f"[BRAND_VOCAB] Redis cache write failed: {e}")

            return categories

        except Exception as e:
            logger.error(
                f"[BRAND_VOCAB] ✗ Failed to query allowed categories: {e}",
                exc_info=True,
            )
            return []

    def get_allowed_styles(self, brand_no: str, use_cache: bool = True) -> List[str]:
        """
        获取品牌的 allowed styles。
        
        Args:
            brand_no: 品牌编码
            use_cache: 是否使用缓存
        
        Returns:
            style_name 列表（where is_active=1）
        """
        cache_key = f"vocab:{brand_no}:styles"
        
        # 检查内存缓存
        if use_cache and cache_key in self._memory_cache:
            value, expires_at = self._memory_cache[cache_key]
            if datetime.now() < expires_at:
                return value
            else:
                del self._memory_cache[cache_key]

        # 检查 Redis 缓存
        redis_client = None
        try:
            if settings.redis_url:
                redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                redis_client.ping()
        except Exception:
            redis_client = None

        if use_cache and redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    import json
                    styles = json.loads(cached)
                    self._memory_cache[cache_key] = (
                        styles,
                        datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS),
                    )
                    return styles
            except Exception:
                pass

        # 从数据库查询
        logger.info(f"[BRAND_VOCAB] Querying allowed styles for brand_no={brand_no}")
        try:
            sql = """
            SELECT DISTINCT style_name
            FROM product_styles
            WHERE brand_no = :brand_no
              AND is_active = 1
              AND style_name IS NOT NULL
              AND style_name != ''
            ORDER BY style_name
            """
            result = self.db.execute(text(sql), {"brand_no": brand_no})
            styles = [row[0] for row in result if row[0]]

            # 更新缓存
            expires_at = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
            self._memory_cache[cache_key] = (styles, expires_at)

            if redis_client:
                try:
                    import json
                    redis_client.setex(
                        cache_key,
                        CACHE_TTL_SECONDS,
                        json.dumps(styles, ensure_ascii=False),
                    )
                except Exception:
                    pass

            return styles

        except Exception as e:
            logger.error(f"[BRAND_VOCAB] ✗ Failed to query allowed styles: {e}", exc_info=True)
            return []

    def get_allowed_seasons(self, brand_no: str, use_cache: bool = True) -> List[str]:
        """
        获取品牌的 allowed seasons。
        
        Args:
            brand_no: 品牌编码
            use_cache: 是否使用缓存
        
        Returns:
            season_name 列表
        """
        cache_key = f"vocab:{brand_no}:seasons"
        
        # 检查内存缓存
        if use_cache and cache_key in self._memory_cache:
            value, expires_at = self._memory_cache[cache_key]
            if datetime.now() < expires_at:
                return value
            else:
                del self._memory_cache[cache_key]

        # 检查 Redis 缓存
        redis_client = None
        try:
            if settings.redis_url:
                redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                redis_client.ping()
        except Exception:
            redis_client = None

        if use_cache and redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    import json
                    seasons = json.loads(cached)
                    self._memory_cache[cache_key] = (
                        seasons,
                        datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS),
                    )
                    return seasons
            except Exception:
                pass

        # 从数据库查询
        logger.info(f"[BRAND_VOCAB] Querying allowed seasons for brand_no={brand_no}")
        try:
            sql = """
            SELECT DISTINCT season_name
            FROM product_seasons
            WHERE brand_no = :brand_no
              AND season_name IS NOT NULL
              AND season_name != ''
            ORDER BY season_name
            """
            result = self.db.execute(text(sql), {"brand_no": brand_no})
            seasons = [row[0] for row in result if row[0]]

            # 更新缓存
            expires_at = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
            self._memory_cache[cache_key] = (seasons, expires_at)

            if redis_client:
                try:
                    import json
                    redis_client.setex(
                        cache_key,
                        CACHE_TTL_SECONDS,
                        json.dumps(seasons, ensure_ascii=False),
                    )
                except Exception:
                    pass

            return seasons

        except Exception as e:
            logger.error(f"[BRAND_VOCAB] ✗ Failed to query allowed seasons: {e}", exc_info=True)
            return []

    def get_allowed_colors(self, brand_no: str, use_cache: bool = True) -> List[str]:
        """
        获取品牌的 allowed colors。
        
        Args:
            brand_no: 品牌编码
            use_cache: 是否使用缓存
        
        Returns:
            color_name 列表
        """
        cache_key = f"vocab:{brand_no}:colors"
        
        # 检查内存缓存
        if use_cache and cache_key in self._memory_cache:
            value, expires_at = self._memory_cache[cache_key]
            if datetime.now() < expires_at:
                return value
            else:
                del self._memory_cache[cache_key]

        # 检查 Redis 缓存
        redis_client = None
        try:
            if settings.redis_url:
                redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                redis_client.ping()
        except Exception:
            redis_client = None

        if use_cache and redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    import json
                    colors = json.loads(cached)
                    self._memory_cache[cache_key] = (
                        colors,
                        datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS),
                    )
                    return colors
            except Exception:
                pass

        # 从数据库查询
        logger.info(f"[BRAND_VOCAB] Querying allowed colors for brand_no={brand_no}")
        try:
            sql = """
            SELECT DISTINCT color_name
            FROM product_colors
            WHERE brand_no = :brand_no
              AND color_name IS NOT NULL
              AND color_name != ''
            ORDER BY color_name
            """
            result = self.db.execute(text(sql), {"brand_no": brand_no})
            colors = [row[0] for row in result if row[0]]

            # 更新缓存
            expires_at = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
            self._memory_cache[cache_key] = (colors, expires_at)

            if redis_client:
                try:
                    import json
                    redis_client.setex(
                        cache_key,
                        CACHE_TTL_SECONDS,
                        json.dumps(colors, ensure_ascii=False),
                    )
                except Exception:
                    pass

            return colors

        except Exception as e:
            logger.error(f"[BRAND_VOCAB] ✗ Failed to query allowed colors: {e}", exc_info=True)
            return []

    def get_allowed_genders(self, brand_no: str, use_cache: bool = True) -> List[str]:
        """
        获取品牌的 allowed genders。
        
        Args:
            brand_no: 品牌编码
            use_cache: 是否使用缓存
        
        Returns:
            gender_name 列表
        """
        cache_key = f"vocab:{brand_no}:genders"
        
        # 检查内存缓存
        if use_cache and cache_key in self._memory_cache:
            value, expires_at = self._memory_cache[cache_key]
            if datetime.now() < expires_at:
                return value
            else:
                del self._memory_cache[cache_key]

        # 检查 Redis 缓存
        redis_client = None
        try:
            if settings.redis_url:
                redis_client = redis.from_url(settings.redis_url, decode_responses=True)
                redis_client.ping()
        except Exception:
            redis_client = None

        if use_cache and redis_client:
            try:
                cached = redis_client.get(cache_key)
                if cached:
                    import json
                    genders = json.loads(cached)
                    self._memory_cache[cache_key] = (
                        genders,
                        datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS),
                    )
                    return genders
            except Exception:
                pass

        # 从数据库查询
        logger.info(f"[BRAND_VOCAB] Querying allowed genders for brand_no={brand_no}")
        try:
            sql = """
            SELECT DISTINCT gender_name
            FROM product_genders
            WHERE brand_no = :brand_no
              AND gender_name IS NOT NULL
              AND gender_name != ''
            ORDER BY gender_name
            """
            result = self.db.execute(text(sql), {"brand_no": brand_no})
            genders = [row[0] for row in result if row[0]]

            # 更新缓存
            expires_at = datetime.now() + timedelta(seconds=CACHE_TTL_SECONDS)
            self._memory_cache[cache_key] = (genders, expires_at)

            if redis_client:
                try:
                    import json
                    redis_client.setex(
                        cache_key,
                        CACHE_TTL_SECONDS,
                        json.dumps(genders, ensure_ascii=False),
                    )
                except Exception:
                    pass

            return genders

        except Exception as e:
            logger.error(f"[BRAND_VOCAB] ✗ Failed to query allowed genders: {e}", exc_info=True)
            return []

    def get_all_allowed_enums(self, brand_no: str) -> Dict[str, List[str]]:
        """
        一次性获取所有 allowed enums（用于 prompt 构建）。
        
        Args:
            brand_no: 品牌编码
        
        Returns:
            Dict with keys: categories, styles, seasons, colors, genders
        """
        return {
            "categories": self.get_allowed_categories(brand_no),
            "styles": self.get_allowed_styles(brand_no),
            "seasons": self.get_allowed_seasons(brand_no),
            "colors": self.get_allowed_colors(brand_no),
            "genders": self.get_allowed_genders(brand_no),
        }


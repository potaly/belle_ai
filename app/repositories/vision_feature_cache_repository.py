"""Vision feature cache repository (V6.0.0+).

支持 Redis 和 MySQL 两种存储方式，自动适配。
优先级：Redis > MySQL
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Redis client (lazy import)
_redis_client = None


def _get_redis_client():
    """获取 Redis 客户端（懒加载）。"""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        import redis
        settings = get_settings()
        if not settings.redis_url:
            logger.warning("[CACHE] Redis URL not configured, will use MySQL fallback")
            return None

        # 解析 Redis URL: redis://host:port/db
        redis_url = settings.redis_url
        if redis_url.startswith("redis://"):
            redis_url = redis_url[8:]  # 去掉 redis:// 前缀

        parts = redis_url.split("/")
        host_port = parts[0]
        db = int(parts[1]) if len(parts) > 1 else 0

        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 6379

        _redis_client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        # 测试连接
        _redis_client.ping()
        logger.info(f"[CACHE] ✓ Redis connected: {host}:{port}/{db}")
        return _redis_client
    except Exception as e:
        logger.warning(f"[CACHE] Redis connection failed: {e}, will use MySQL fallback")
        _redis_client = None
        return None


class VisionFeatureCacheRepository:
    """视觉特征缓存仓库。"""

    @staticmethod
    def generate_trace_id() -> str:
        """生成全局唯一的 trace_id。"""
        return f"vision_{uuid.uuid4().hex[:16]}_{int(datetime.now().timestamp())}"

    @staticmethod
    def save(
        db: Session,
        trace_id: str,
        brand_code: str,
        scene: str,
        vision_features: Dict,
        ttl_hours: int = 24,
    ) -> bool:
        """
        保存 trace_id -> vision_features 映射。
        
        Args:
            db: Database session
            trace_id: 追踪ID
            brand_code: 品牌编码
            scene: 使用场景
            vision_features: 视觉特征字典
            ttl_hours: 过期时间（小时，默认24）
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"[CACHE] Saving trace_id={trace_id}, brand_code={brand_code}, scene={scene}")

        # 尝试使用 Redis
        redis_client = _get_redis_client()
        if redis_client:
            try:
                cache_data = {
                    "brand_code": brand_code,
                    "scene": scene,
                    "vision_features": vision_features,
                    "created_at": datetime.now().isoformat(),
                }
                redis_key = f"vision_feature:{trace_id}"
                redis_client.setex(
                    redis_key,
                    ttl_hours * 3600,  # TTL in seconds
                    json.dumps(cache_data, ensure_ascii=False),
                )
                logger.info(f"[CACHE] ✓ Saved to Redis: {trace_id}")
                return True
            except Exception as e:
                logger.warning(f"[CACHE] Redis save failed: {e}, falling back to MySQL")
                # Fall through to MySQL

        # 使用 MySQL 作为降级方案
        try:
            expires_at = datetime.now() + timedelta(hours=ttl_hours)
            sql = """
            INSERT INTO vision_feature_cache 
            (trace_id, brand_code, scene, vision_features_json, created_at, expires_at)
            VALUES 
            (:trace_id, :brand_code, :scene, :vision_features_json, NOW(), :expires_at)
            ON DUPLICATE KEY UPDATE
                brand_code = VALUES(brand_code),
                scene = VALUES(scene),
                vision_features_json = VALUES(vision_features_json),
                created_at = NOW(),
                expires_at = VALUES(expires_at)
            """
            db.execute(
                text(sql),
                {
                    "trace_id": trace_id,
                    "brand_code": brand_code,
                    "scene": scene,
                    "vision_features_json": json.dumps(vision_features, ensure_ascii=False),
                    "expires_at": expires_at,
                },
            )
            db.commit()
            logger.info(f"[CACHE] ✓ Saved to MySQL: {trace_id}")
            return True
        except Exception as e:
            logger.error(f"[CACHE] ✗ MySQL save failed: {e}", exc_info=True)
            db.rollback()
            return False

    @staticmethod
    def get(
        db: Session,
        trace_id: str,
    ) -> Optional[Dict]:
        """
        获取 trace_id 对应的 vision_features。
        
        Args:
            db: Database session
            trace_id: 追踪ID
        
        Returns:
            Dict with keys: brand_code, scene, vision_features
            None if not found or expired
        """
        logger.info(f"[CACHE] Getting trace_id={trace_id}")

        # 尝试从 Redis 获取
        redis_client = _get_redis_client()
        if redis_client:
            try:
                redis_key = f"vision_feature:{trace_id}"
                cached_data = redis_client.get(redis_key)
                if cached_data:
                    data = json.loads(cached_data)
                    logger.info(f"[CACHE] ✓ Retrieved from Redis: {trace_id}")
                    return data
            except Exception as e:
                logger.warning(f"[CACHE] Redis get failed: {e}, falling back to MySQL")
                # Fall through to MySQL

        # 从 MySQL 获取
        try:
            sql = """
            SELECT brand_code, scene, vision_features_json, expires_at
            FROM vision_feature_cache
            WHERE trace_id = :trace_id AND expires_at > NOW()
            """
            result = db.execute(text(sql), {"trace_id": trace_id})
            row = result.fetchone()
            if row:
                data = {
                    "brand_code": row[0],
                    "scene": row[1],
                    "vision_features": json.loads(row[2]),
                    "created_at": row[3].isoformat() if hasattr(row[3], "isoformat") else str(row[3]),
                }
                logger.info(f"[CACHE] ✓ Retrieved from MySQL: {trace_id}")
                return data
            else:
                logger.warning(f"[CACHE] ✗ Trace ID not found or expired: {trace_id}")
                return None
        except Exception as e:
            logger.error(f"[CACHE] ✗ MySQL get failed: {e}", exc_info=True)
            return None

    @staticmethod
    def delete(db: Session, trace_id: str) -> bool:
        """
        删除 trace_id 对应的缓存。
        
        Args:
            db: Database session
            trace_id: 追踪ID
        
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"[CACHE] Deleting trace_id={trace_id}")

        # 尝试从 Redis 删除
        redis_client = _get_redis_client()
        if redis_client:
            try:
                redis_key = f"vision_feature:{trace_id}"
                redis_client.delete(redis_key)
                logger.info(f"[CACHE] ✓ Deleted from Redis: {trace_id}")
            except Exception as e:
                logger.warning(f"[CACHE] Redis delete failed: {e}")

        # 从 MySQL 删除
        try:
            sql = "DELETE FROM vision_feature_cache WHERE trace_id = :trace_id"
            db.execute(text(sql), {"trace_id": trace_id})
            db.commit()
            logger.info(f"[CACHE] ✓ Deleted from MySQL: {trace_id}")
            return True
        except Exception as e:
            logger.error(f"[CACHE] ✗ MySQL delete failed: {e}", exc_info=True)
            db.rollback()
            return False


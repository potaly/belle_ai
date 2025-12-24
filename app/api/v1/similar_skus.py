"""Similar SKUs search API endpoints (V6.0.0+)."""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.similar_skus import SimilarSKUsRequest, SimilarSKUsResponse
from app.services.log_service import (
    log_similar_skus_called,
    log_similar_skus_fallback,
    log_similar_skus_traceid_miss,
)
from app.services.similar_skus_service import SimilarSKUsService
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/product", tags=["ai"])

# Global service instance
_similar_skus_service: Optional[SimilarSKUsService] = None


def get_similar_skus_service() -> SimilarSKUsService:
    """Get or create the global similar SKUs service instance."""
    global _similar_skus_service
    if _similar_skus_service is None:
        vector_store = VectorStore()
        vector_store.load()  # Try to load, but don't fail if not available
        _similar_skus_service = SimilarSKUsService(vector_store=vector_store)
    return _similar_skus_service


@router.post("/similar_skus", response_model=SimilarSKUsResponse)
async def search_similar_skus(
    request: SimilarSKUsRequest,
    db: Session = Depends(get_db),
) -> SimilarSKUsResponse:
    """
    相似商品检索接口（V6.0.0+）。
    
    阶段目标：给导购一个备选池（最多5个SKU）。
    
    硬约束：
    1. 主键维度必须包含 brand_code，禁止只用 sku
    2. 默认只返回 5 个 sku（top_k<=5），不足 5 条允许少于 5 条
    3. 禁止访问 chihiro（只用 belle_ai.products / 向量库接口）
    4. 支持两种检索模式：
       - mode=rule（默认）：从 products 表规则筛选 + 简单打分排序
       - mode=vector（可选）：向量检索 top_k（如果向量库可用）
    5. 必须去重：按 (brand_code, sku) 去重
    6. 不返回价格/促销/库存（保持接口极简）
    
    参数说明:
        request: 相似SKU检索请求体
            - brand_code: 品牌编码（必需）
            - top_k: 返回结果数量（最多5个，默认5）
            - vision_features: 视觉特征（来自Step 1）
            - mode: 检索模式（rule/vector，默认rule）
        db: 数据库会话
    
    返回值:
        SimilarSKUsResponse，包含：
        - similar_skus: SKU列表（最多5个）
    """
    start_time = time.time()

    logger.info("=" * 80)
    logger.info("[API] POST /ai/product/similar_skus - Request received")
    logger.info(
        f"[API] Request: brand_code={request.brand_code}, top_k={request.top_k}, mode={request.mode}"
    )
    logger.info(
        f"[API] Input: trace_id={request.trace_id}, vision_features={'provided' if request.vision_features else 'none'}"
    )

    try:
        # Validate mode
        if request.mode not in ("rule", "vector"):
            logger.warning(f"[API] ✗ Invalid mode: {request.mode}, using 'rule'")
            request.mode = "rule"

        # Convert vision_features to dict (if provided)
        vision_features_dict = None
        if request.vision_features:
            vision_features_dict = {
                "category": request.vision_features.category,
                "style": request.vision_features.style or [],
                "color": request.vision_features.color,
                "colors": [],  # Will be populated from vision_features if available
                "season": request.vision_features.season,
                "keywords": request.vision_features.keywords or [],
            }
            # If vision_features has colors, use it
            if hasattr(request.vision_features, "colors") and request.vision_features.colors:
                vision_features_dict["colors"] = request.vision_features.colors

        # Get service
        service = get_similar_skus_service()

        # Search
        logger.info("[API] Step 1: Calling similar SKUs service...")
        try:
            skus, fallback_used = await service.search_similar_skus(
                db=db,
                brand_code=request.brand_code,
                vision_features=vision_features_dict,
                trace_id=request.trace_id,
                top_k=request.top_k,
                mode=request.mode,
            )
        except ValueError as e:
            # Handle trace_id resolution failure
            if "trace_id" in str(e).lower() or "not found" in str(e).lower():
                logger.warning(f"[API] ✗ Trace ID resolution failed: {e}")
                latency_ms = int((time.time() - start_time) * 1000)
                await log_similar_skus_traceid_miss(
                    trace_id=request.trace_id or "",
                    latency_ms=latency_ms,
                )
                return SimilarSKUsResponse(
                    success=False,
                    data=None,
                    message="trace_id not found or expired",
                )
            raise
        
        logger.info(f"[API] ✓ Search completed: {len(skus)} SKUs")

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Log events
        logger.info("[API] Step 2: Logging events...")
        await log_similar_skus_called(
            brand_code=request.brand_code,
            mode=request.mode,
            top_k=request.top_k,
            candidate_count=0,  # Will be set in service if needed
            result_count=len(skus),
            trace_id=request.trace_id,
            latency_ms=latency_ms,
        )

        if fallback_used:
            await log_similar_skus_fallback(
                brand_code=request.brand_code,
                from_mode="vector",
                to_mode="rule",
                latency_ms=latency_ms,
            )

        logger.info(
            f"[API] ✓ Similar SKUs search completed: "
            f"brand_code={request.brand_code}, result_count={len(skus)}, "
            f"fallback_used={fallback_used}, latency={latency_ms}ms"
        )
        logger.info("=" * 80)

        return SimilarSKUsResponse(
            success=True,
            data={"similar_skus": skus},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] ✗ Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


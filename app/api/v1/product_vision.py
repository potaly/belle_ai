"""Product vision analysis API endpoints (V6.0.0+)."""
from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.vision import VisionAnalyzeRequest, VisionAnalyzeResponse
from app.services.log_service import (
    log_guide_copy_generated,
    log_vision_analyze_called,
)
from app.services.vision_analyze_service import VisionAnalyzeService
from app.services.vision_client import VisionClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/product", tags=["ai"])

vision_service = VisionAnalyzeService()


@router.post("/vision_analyze", response_model=VisionAnalyzeResponse)
async def vision_analyze(
    request: VisionAnalyzeRequest,
    db: Session = Depends(get_db),
) -> VisionAnalyzeResponse:
    """
    拍照识图分析接口（V6.0.0+）。
    
    能力定位：导购私聊辅助能力，帮助导购在不知道 SKU 的情况下，拍一张鞋的照片，就能"敢发第一句话"。
    
    重要原则：
    1. 输出必须适合微信私聊场景，而不是广告/详情页文案
    2. 绝对禁止输出：SKU/货号/款号/编码、价格/优惠/促销/库存/链接
    3. 不允许编造无法从图片外观判断的信息：材质（如真皮/科技材料）、功能点（如气垫、防水、保暖）
    4. 语气要求：自然、克制、像真实导购，不夸张
    5. 必须包含"轻提问式引导"，帮助导购开启对话
    
    参数说明:
        image: 图片URL或Base64编码（必需）
        brand_code: 品牌编码（必需）
        scene: 使用场景（固定为guide_chat，默认值）
        db: 数据库会话
    
    返回值:
        VisionAnalyzeResponse，包含：
        - visual_summary: 视觉摘要（基于外观判断）
        - selling_points: 卖点（不编造材质/功能）
        - guide_chat_copy: 导购私聊话术（包含轻提问式引导）
        - tracking: 追踪信息
    """
    start_time = time.time()

    logger.info("=" * 80)
    logger.info("[API] POST /ai/product/vision_analyze - Request received")

    try:
        # Step 1: 处理图片输入
        logger.info("[API] Step 1: Processing image input...")
        image_url: Optional[str] = None
        image_base64: Optional[str] = None

        # 判断是URL还是Base64
        if request.image.startswith("http://") or request.image.startswith("https://"):
            image_url = request.image
            logger.info(f"[API] ✓ Image URL provided: {image_url[:100]}")
        elif request.image.startswith("data:image"):
            image_base64 = request.image
            logger.info(f"[API] ✓ Image Base64 provided: {len(image_base64)} chars")
        else:
            # 假设是纯Base64字符串
            image_base64 = request.image
            logger.info(f"[API] ✓ Image Base64 provided (plain): {len(image_base64)} chars")

        # Step 2: 验证参数（scene 已在 Schema 中验证）
        if not request.brand_code:
            logger.warning("[API] ✗ brand_code is required")
            raise HTTPException(status_code=400, detail="brand_code 是必需的")

        logger.info(
            f"[API] Request parameters: brand_code={request.brand_code}, scene={request.scene}"
        )

        # Step 3: 调用视觉分析服务
        logger.info("[API] Step 2: Calling vision analysis service...")
        data = await vision_service.analyze(
            image_url=image_url,
            image_base64=image_base64,
            brand_code=request.brand_code,
        )
        logger.info("[API] ✓ Vision analysis completed")

        # Step 4: 计算耗时
        latency_ms = int((time.time() - start_time) * 1000)

        # Step 5: 埋点
        logger.info("[API] Step 3: Logging events...")
        await log_vision_analyze_called(
            brand_code=request.brand_code,
            scene=request.scene,
            vision_used=data.tracking.vision_used,
            latency_ms=latency_ms,
        )
        await log_guide_copy_generated(
            brand_code=request.brand_code,
            scene=request.scene,
            primary_copy=data.guide_chat_copy.primary,
            alternatives_count=len(data.guide_chat_copy.alternatives),
            vision_used=data.tracking.vision_used,
            latency_ms=latency_ms,
        )
        logger.info("[API] ✓ Events logged")

        logger.info(
            f"[API] ✓ Vision analysis completed: "
            f"category={data.visual_summary.category_guess}, "
            f"primary_copy_length={len(data.guide_chat_copy.primary)}, "
            f"latency={latency_ms}ms"
        )
        logger.info("=" * 80)

        return VisionAnalyzeResponse(
            success=True,
            data=data,
        )

    except HTTPException:
        raise
    except VisionClientError as e:
        logger.error(f"[API] ✗ Vision client error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"视觉分析失败: {str(e)}")
    except Exception as e:
        logger.error(f"[API] ✗ Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


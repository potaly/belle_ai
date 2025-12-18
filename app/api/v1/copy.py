"""Copy generation API endpoints (V5.5.0+).

商品维度话术生成接口（无用户）：
- 输入：SKU + scene 参数
- 输出：商品卖点 + 多条话术候选
- 不涉及用户行为、意图分析、销售决策
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.product_repository import get_product_by_sku
from app.schemas.copy_schemas import (
    CopyCandidateSchema,
    CopyRequest,
    CopyResponse,
    CopyScene,
    CopyStyle,
)
from app.services.log_service import log_ai_task
from app.services.product_copy_service import generate_product_copy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate/copy", response_model=CopyResponse)
async def generate_copy(
    request: CopyRequest,
    db: Session = Depends(get_db),
    guide_id: str | None = None,
) -> CopyResponse:
    """
    生成商品话术（商品维度，无用户）。
    
    核心职责：
    - 基于商品数据生成话术候选
    - 支持不同场景（guide_chat / moments / poster）
    - 支持不同风格（natural / professional / friendly）
    - 不涉及用户行为、意图分析、销售决策
    
    参数说明:
        request: 话术生成请求体
        db: 数据库 session
        guide_id: 导购员 ID（可选，用于日志）
    
    返回值:
        CopyResponse: 包含商品卖点和话术候选的结构化响应
        
    请求示例:
        ```json
        {
            "sku": "8WZ01CM1",
            "scene": "guide_chat",
            "style": "natural",
            "use_case": "product_only"
        }
        ```
    """
    logger.info("=" * 80)
    logger.info("[API] POST /ai/generate/copy - Request received (V5.5.0+)")
    logger.info(
        f"[API] Request: sku={request.sku}, scene={request.scene}, "
        f"style={request.style}, use_case={request.use_case}"
    )
    
    start_time = time.time()
    task_id = str(uuid.uuid4())
    
    try:
        # Step 1: Load product
        logger.info("[API] Step 1: Loading product from database...")
        product = get_product_by_sku(db, request.sku)
        if not product:
            logger.error(f"[API] ✗ Product not found: sku={request.sku}")
            raise HTTPException(
                status_code=404, detail=f"Product with SKU {request.sku} not found"
            )
        logger.info(f"[API] ✓ Product loaded: {product.name}")
        
        # Step 2: Determine scene and style
        # Map legacy "funny" to "friendly"
        style_map = {
            CopyStyle.natural: "natural",
            CopyStyle.professional: "professional",
            CopyStyle.funny: "friendly",  # Legacy mapping
        }
        actual_style = style_map.get(request.style, "natural")
        
        # Use scene from request or default
        scene = request.scene.value if request.scene else "guide_chat"
        
        # Step 3: Generate product copy
        logger.info(f"[API] Step 2: Generating product copy (scene={scene}, style={actual_style})...")
        candidates = await generate_product_copy(
            product=product,
            scene=scene,
            style=actual_style,
            max_length=50,  # Default max length
        )
        
        logger.info(f"[API] ✓ Generated {len(candidates)} copy candidates")
        
        # Step 4: Extract selling points (from analysis service)
        from app.services.product_analysis_service import analyze_selling_points
        
        selling_points = analyze_selling_points(product, use_llm=True)
        logger.info(f"[API] ✓ Extracted {len(selling_points)} selling points")
        
        # Step 5: Build response
        execution_time = time.time() - start_time
        
        # Convert candidates to schema
        candidate_schemas = [
            CopyCandidateSchema(
                scene=candidate.scene,
                style=candidate.style,
                message=candidate.message,
            )
            for candidate in candidates
        ]
        
        # Backward compatible: extract messages for "posts" field
        posts = [candidate.message for candidate in candidates]
        
        response = CopyResponse(
            sku=product.sku,
            product_name=product.name,
            selling_points=selling_points,
            copy_candidates=candidate_schemas,
            posts=posts,  # Backward compatible
        )
        
        # Step 6: Log task (async)
        try:
            input_data = {
                "sku": request.sku,
                "product_name": product.name,
                "scene": scene,
                "style": actual_style,
                "use_case": request.use_case.value if request.use_case else "product_only",
            }
            output_data = {
                "task_id": task_id,
                "selling_points_count": len(selling_points),
                "copy_candidates_count": len(candidates),
                "execution_time_seconds": round(execution_time, 3),
            }
            
            asyncio.create_task(
                log_ai_task(
                    db=db,
                    task_type="generate_product_copy",
                    input_data=input_data,
                    output_data=output_data,
                    task_id=task_id,
                )
            )
        except Exception as e:
            logger.warning(f"[API] Failed to log task: {e}")
        
        logger.info(
            f"[API] ✓ Request processed successfully in {execution_time:.3f}s. "
            f"Selling points: {len(selling_points)}, Candidates: {len(candidates)}"
        )
        logger.info("=" * 80)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        execution_time = time.time() - start_time
        logger.error(
            f"[API] ✗ Request failed after {execution_time:.3f}s: {e}",
            exc_info=True,
        )
        logger.info("=" * 80)
        raise HTTPException(status_code=500, detail=f"Failed to generate copy: {str(e)}")

"""Service for logging AI tasks."""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.ai_task_log import AITaskLog

logger = logging.getLogger(__name__)


async def log_ai_task(
    scene_type: str,
    input_data: Dict[str, Any],
    output_result: Optional[Dict[str, Any]] = None,
    guide_id: Optional[str] = None,
    model_name: Optional[str] = None,
    latency_ms: Optional[int] = None,
    task_id: Optional[str] = None,
    prompt_token_estimate: Optional[int] = None,
    output_token_estimate: Optional[int] = None,
    rag_used: Optional[bool] = None,
) -> str:
    """
    Asynchronously log an AI task to the database.
    
    Args:
        scene_type: Type of AI task (copy, product_analyze, intent)
        input_data: Input data as dictionary
        output_result: Output result as dictionary (optional)
        guide_id: Guide ID (optional)
        model_name: Model name used (optional)
        latency_ms: Request latency in milliseconds (optional)
        task_id: Task ID (optional, will be generated if not provided)
        
    Returns:
        Task ID
    """
    if task_id is None:
        task_id = str(uuid.uuid4())
    
    logger.info(f"[LOG_SERVICE] ========== Logging AI Task ==========")
    logger.info(f"[LOG_SERVICE] Task ID: {task_id}")
    logger.info(f"[LOG_SERVICE] Input parameters:")
    logger.info(f"[LOG_SERVICE]   - scene_type: {scene_type}")
    logger.info(f"[LOG_SERVICE]   - guide_id: {guide_id}")
    logger.info(f"[LOG_SERVICE]   - model_name: {model_name}")
    logger.info(f"[LOG_SERVICE]   - latency_ms: {latency_ms}")
    logger.info(f"[LOG_SERVICE]   - prompt_token_estimate: {prompt_token_estimate}")
    logger.info(f"[LOG_SERVICE]   - output_token_estimate: {output_token_estimate}")
    logger.info(f"[LOG_SERVICE]   - rag_used: {rag_used}")
    logger.info(f"[LOG_SERVICE] Input data: {json.dumps(input_data, ensure_ascii=False, indent=2)}")
    if output_result:
        logger.info(f"[LOG_SERVICE] Output result: {json.dumps(output_result, ensure_ascii=False, indent=2)}")
    
    # Add token estimates and RAG info to output_result if not present
    if output_result is None:
        output_result = {}
    
    if prompt_token_estimate is not None and "prompt_token_estimate" not in output_result:
        output_result["prompt_token_estimate"] = prompt_token_estimate
    if output_token_estimate is not None and "output_token_estimate" not in output_result:
        output_result["output_token_estimate"] = output_token_estimate
    if rag_used is not None and "rag_used" not in output_result:
        output_result["rag_used"] = rag_used
    
    # Run database operation in thread pool to avoid blocking
    def _save_log():
        db = SessionLocal()
        try:
            logger.info(f"[LOG_SERVICE] Saving to database...")
            log_entry = AITaskLog(
                task_id=task_id,
                guide_id=guide_id,
                scene_type=scene_type,
                input_data=json.dumps(input_data, ensure_ascii=False),
                output_result=json.dumps(output_result, ensure_ascii=False) if output_result else None,
                model_name=model_name,
                latency_ms=latency_ms,
                is_adopted=False,
            )
            db.add(log_entry)
            db.commit()
            logger.info(f"[LOG_SERVICE] ✓ AI task logged successfully: task_id={task_id}, scene_type={scene_type}")
        except Exception as e:
            logger.error(f"[LOG_SERVICE] ✗ Failed to log AI task: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()
    
    # Execute in thread pool
    logger.info(f"[LOG_SERVICE] Executing database save in thread pool...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _save_log)
    logger.info(f"[LOG_SERVICE] ========== Logging Completed ==========")
    
    return task_id


async def log_vision_analyze_called(
    brand_code: str,
    scene: str,
    trace_id: Optional[str] = None,
    vision_used: bool = True,
    latency_ms: Optional[int] = None,
    confidence_level: Optional[str] = None,
) -> None:
    """
    埋点：视觉分析接口被调用。
    
    Args:
        brand_code: 品牌编码
        scene: 使用场景
        trace_id: 追踪ID（新增）
        vision_used: 是否使用了视觉模型
        latency_ms: 耗时（毫秒）
        confidence_level: 置信度级别（新增）
    """
    await log_ai_task(
        scene_type="vision_analyze_called",
        input_data={
            "brand_code": brand_code,
            "scene": scene,
            "trace_id": trace_id,
            "vision_used": vision_used,
            "confidence_level": confidence_level,
        },
        latency_ms=latency_ms,
    )


async def log_guide_copy_generated(
    brand_code: str,
    scene: str,
    trace_id: Optional[str] = None,
    primary_copy: str = "",
    alternatives_count: int = 0,
    vision_used: bool = True,
    latency_ms: Optional[int] = None,
) -> None:
    """
    埋点：导购话术生成。
    
    Args:
        brand_code: 品牌编码
        scene: 使用场景
        trace_id: 追踪ID（新增）
        primary_copy: 主要话术
        alternatives_count: 备选话术数量
        vision_used: 是否使用了视觉模型
        latency_ms: 耗时（毫秒）
    """
    await log_ai_task(
        scene_type="guide_copy_generated",
        input_data={
            "brand_code": brand_code,
            "scene": scene,
            "trace_id": trace_id,
            "vision_used": vision_used,
        },
        output_result={
            "primary_copy": primary_copy,
            "alternatives_count": alternatives_count,
        },
        latency_ms=latency_ms,
    )


async def log_similar_skus_called(
    brand_code: str,
    mode: str,
    top_k: int,
    candidate_count: int,
    result_count: int,
    trace_id: Optional[str] = None,
    latency_ms: Optional[int] = None,
) -> None:
    """
    埋点：相似SKU检索接口被调用。
    
    Args:
        brand_code: 品牌编码
        mode: 检索模式（rule/vector）
        top_k: 请求的top_k
        candidate_count: 候选商品数量
        result_count: 返回结果数量
        trace_id: 追踪ID（新增）
        latency_ms: 耗时（毫秒）
    """
    await log_ai_task(
        scene_type="similar_skus_called",
        input_data={
            "brand_code": brand_code,
            "mode": mode,
            "top_k": top_k,
            "candidate_count": candidate_count,
            "trace_id": trace_id,
        },
        output_result={
            "result_count": result_count,
        },
        latency_ms=latency_ms,
    )


async def log_similar_skus_traceid_miss(
    trace_id: str,
    latency_ms: Optional[int] = None,
) -> None:
    """
    埋点：相似SKU检索 trace_id 缓存未命中。
    
    Args:
        trace_id: 追踪ID
        latency_ms: 耗时（毫秒）
    """
    await log_ai_task(
        scene_type="similar_skus_traceid_miss",
        input_data={
            "trace_id": trace_id,
        },
        latency_ms=latency_ms,
    )


async def log_similar_skus_fallback(
    brand_code: str,
    from_mode: str,
    to_mode: str,
    latency_ms: Optional[int] = None,
) -> None:
    """
    埋点：相似SKU检索降级（vector->rule）。
    
    Args:
        brand_code: 品牌编码
        from_mode: 原始模式
        to_mode: 降级后的模式
        latency_ms: 耗时（毫秒）
    """
    await log_ai_task(
        scene_type="similar_skus_fallback",
        input_data={
            "brand_code": brand_code,
            "from_mode": from_mode,
            "to_mode": to_mode,
        },
        latency_ms=latency_ms,
    )


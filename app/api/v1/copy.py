"""Copy generation API endpoints."""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.copy_schemas import CopyRequest, CopyStyle
from app.services.copy_service import prepare_copy_generation
from app.services.llm_client import get_llm_client, LLMClientError
from app.services.log_service import log_ai_task
from app.services.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate/copy")
async def generate_copy(
    request: CopyRequest,
    db: Session = Depends(get_db),
    guide_id: str | None = None,
) -> StreamingResponse:
    """
    生成产品朋友圈文案（流式 SSE）。

    本接口通过 Server-Sent Events (SSE) 实时流式生成朋友圈文案。
    第一个响应 chunk 会在 500ms 内返回。

    参数说明:
        request: 文案生成请求体
        db: 数据库 session
        guide_id: 导购员 ID（可选，可从 headers/auth 提取）

    返回值:
        支持 SSE 的 StreamingResponse
    """
 
    logger.info("=" * 80)
    logger.info("[API] POST /ai/generate/copy - Request received")
    logger.info(f"[API] Request parameters: sku={request.sku}, style={request.style.value}, guide_id={guide_id}")
    logger.info(f"[API] Request body: {request.model_dump()}")
    
    try:
        logger.info("[API] Step 1: Preparing copy generation (load product, RAG, build prompt)...")
        start_time = time.time()
        task_id = str(uuid.uuid4())
        
        # Prepare: load product, retrieve RAG, build prompt
        product, prompt, prompt_tokens, rag_used, rag_context, model_name = prepare_copy_generation(
            db=db,
            sku=request.sku,
            style=request.style,
        )
        
        # Prepare input data for logging
        input_data = {
            "sku": request.sku,
            "product_name": product.name,
            "tags": product.tags,
            "style": request.style.value,
            "rag_used": rag_used,
            "rag_context_count": len(rag_context),
        }
        
        logger.info("[API] Step 3: Creating streaming response with LLM...")
        llm_client = get_llm_client()
        system_prompt = "你是一个专业的鞋类销售文案写手，擅长写吸引人的朋友圈文案。"
        
        async def generate_sse_stream():
            """Generate SSE-formatted stream from LLM."""
            full_response = ""
            chunk_count = 0
            
            try:
                async for chunk in llm_client.stream_chat(
                    prompt,
                    system=system_prompt,
                    temperature=0.8,
                    max_tokens=200,
                ):
                    if chunk:
                        full_response += chunk
                        chunk_count += 1
                        # Wrap in SSE format
                        yield f"data: {chunk}\n\n"
                        
                        if chunk_count <= 3:
                            logger.debug(f"[API] Chunk #{chunk_count}: {chunk[:50]}...")
            except LLMClientError as e:
                logger.error(f"[API] ✗ LLM streaming failed: {e}")
                error_msg = "抱歉，文案生成失败，请稍后重试。"
                yield f"data: {error_msg}\n\n"
                full_response = error_msg
            
            # Calculate metrics after streaming completes
            latency_ms = int((time.time() - start_time) * 1000)
            output_tokens = PromptBuilder.estimate_tokens(full_response)
            
            logger.info(f"[API] Step 4: Streaming completed. Chunks: {chunk_count}, Latency: {latency_ms}ms")
            logger.info(f"[API] Generated response: {len(full_response)} chars, ~{output_tokens} tokens")
            
            # Log task asynchronously
            output_data = {
                "task_id": task_id,
                "latency_ms": latency_ms,
                "response": full_response,
                "response_length": len(full_response),
                "prompt_token_estimate": prompt_tokens,
                "output_token_estimate": output_tokens,
                "rag_used": rag_used,
                "rag_context_count": len(rag_context),
            }
            
            asyncio.create_task(
                log_ai_task(
                    scene_type="copy",
                    input_data=input_data,
                    output_result=output_data,
                    guide_id=guide_id,
                    model_name=model_name,
                    latency_ms=latency_ms,
                    task_id=task_id,
                    prompt_token_estimate=prompt_tokens,
                    output_token_estimate=output_tokens,
                    rag_used=rag_used,
                )
            )
            logger.info("[API] ✓ Task logging initiated (async)")
        
        logger.info("[API] Step 5: Returning StreamingResponse")
        logger.info("[API] ✓ Request processed successfully, streaming started")
        logger.info("=" * 80)
        
        return StreamingResponse(
            generate_sse_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )
    except HTTPException as e:
        # Re-raise HTTP exceptions (like 404)
        logger.error(f"[API] ✗ HTTPException: status={e.status_code}, detail={e.detail}")
        logger.info("=" * 80)
        raise
    except Exception as e:
        logger.error(f"[API] ✗ Unexpected error in generate_copy endpoint: {e}", exc_info=True)
        logger.info("=" * 80)
        raise HTTPException(status_code=500, detail=f"Failed to generate copy: {str(e)}")


"""RAG debugging endpoints for previewing retrieval results."""
from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.schemas.base_schemas import BaseResponse
from app.services.rag_service import get_rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin", "rag-debug"])


class RAGPreviewRequest(BaseModel):
    """Request model for RAG preview endpoint."""

    query: str = Field(..., description="Search query text", min_length=1)
    top_k: int = Field(5, description="Number of top results to return", ge=1, le=20)
    include_processed: bool = Field(
        False,
        description="Whether to include processed results (with business logic) for comparison",
    )


class RAGPreviewChunk(BaseModel):
    """Model for a retrieved chunk with score."""

    chunk: str = Field(..., description="Retrieved text chunk")
    score: float = Field(..., description="Similarity score (L2 distance, lower is better)")
    rank: int = Field(..., description="Rank of this result (1-based)")


class RAGPreviewResponse(BaseResponse[dict]):
    """Response model for RAG preview endpoint."""


def check_debug_mode() -> None:
    """
    Dependency to check if debug mode is enabled.
    
    Raises:
        HTTPException: If debug mode is not enabled
    """
    settings = get_settings()
    if not settings.debug:
        logger.warning("RAG debug endpoint accessed but DEBUG mode is not enabled")
        raise HTTPException(
            status_code=403,
            detail="Debug endpoints are only available when DEBUG=true in environment variables",
        )


@router.post("/rag/preview", response_model=RAGPreviewResponse)
async def rag_preview(
    request: RAGPreviewRequest,
    _debug_check: None = Depends(check_debug_mode),
) -> RAGPreviewResponse:
    """
    Preview RAG retrieval results for debugging.
    
    This endpoint allows developers to test and debug RAG retrieval by:
    - Testing different queries
    - Viewing similarity scores
    - Inspecting retrieved chunks
    
    **Only available when DEBUG=true in environment variables.**
    
    Args:
        request: Preview request with query and top_k
        _debug_check: Dependency to verify debug mode is enabled
    
    Returns:
        RAGPreviewResponse with retrieved chunks and scores
    
    Raises:
        HTTPException: 
            - 403 if DEBUG mode is not enabled
            - 503 if vector store is not loaded
    """
    logger.info("=" * 80)
    logger.info("[RAG_DEBUG] POST /admin/rag/preview - Request received")
    logger.info(f"[RAG_DEBUG] Query: '{request.query}', top_k: {request.top_k}")
    
    # Get RAG service
    rag_service = get_rag_service()
    
    # Check if vector store is available
    if not rag_service.is_available():
        logger.error("[RAG_DEBUG] ✗ Vector store is not loaded")
        raise HTTPException(
            status_code=503,
            detail="Vector store is not loaded. Run 'python app/db/init_vector_store.py' to initialize.",
        )
    
    try:
        # Get vector store directly to access search results with scores
        vector_store = rag_service.vector_store
        
        # Perform raw vector search (no business logic)
        logger.info(f"[RAG_DEBUG] Performing raw vector search...")
        raw_search_results = vector_store.search(request.query, top_k=request.top_k)
        
        # Build raw results
        raw_chunks: List[RAGPreviewChunk] = []
        for rank, (chunk, score) in enumerate(raw_search_results, start=1):
            raw_chunks.append(
                RAGPreviewChunk(
                    chunk=chunk,
                    score=round(score, 4),
                    rank=rank,
                )
            )
        
        # Calculate raw statistics
        raw_scores = [chunk.score for chunk in raw_chunks]
        raw_stats = {
            "total_results": len(raw_chunks),
            "min_score": round(min(raw_scores), 4) if raw_scores else 0.0,
            "max_score": round(max(raw_scores), 4) if raw_scores else 0.0,
            "avg_score": round(sum(raw_scores) / len(raw_scores), 4) if raw_scores else 0.0,
        }
        
        logger.info(
            f"[RAG_DEBUG] ✓ Retrieved {len(raw_chunks)} raw results "
            f"(min_score={raw_stats['min_score']}, max_score={raw_stats['max_score']})"
        )
        
        # Build response data
        response_data = {
            "query": request.query,
            "top_k": request.top_k,
            "raw_results": [chunk.model_dump() for chunk in raw_chunks],
            "raw_statistics": raw_stats,
        }
        
        # Optionally include processed results (with business logic) for comparison
        if request.include_processed:
            logger.info(f"[RAG_DEBUG] Including processed results for comparison...")
            try:
                # Import vector_search functions for processing
                from app.api.v1.vector_search import (
                    extract_keywords_from_query,
                    extract_sku_from_query,
                    keyword_match_score,
                )
                from sqlalchemy.orm import Session
                from app.core.database import SessionLocal
                from app.repositories.product_repository import get_product_by_sku
                
                # Extract keywords and SKU
                extracted_sku = extract_sku_from_query(request.query)
                keywords = extract_keywords_from_query(request.query)
                
                processed_results = []
                
                if extracted_sku:
                    # SKU-based search logic
                    db = SessionLocal()
                    try:
                        product = get_product_by_sku(db, extracted_sku)
                        if product:
                            # Build product chunk
                            text_parts = [f"商品名称：{product.name}", f"商品SKU：{product.sku}"]
                            if product.tags:
                                tags_str = "、".join(product.tags) if isinstance(product.tags, list) else str(product.tags)
                                text_parts.append(f"商品标签：{tags_str}")
                            chunk = f"[商品：{product.name}（SKU：{product.sku}）] {'。'.join(text_parts)}"
                            processed_results = [(chunk, 0.0, "sku_exact_match")]
                        else:
                            processed_results = raw_search_results[:request.top_k]
                    finally:
                        db.close()
                elif keywords["colors"] or keywords["types"] or keywords["attributes"]:
                    # Keyword-based re-ranking
                    vector_results = vector_store.search(request.query, top_k=request.top_k * 2)
                    scored_results = []
                    for chunk, vector_score in vector_results:
                        keyword_score = keyword_match_score(chunk, keywords)
                        combined_score = keyword_score - vector_score
                        scored_results.append((chunk, vector_score, keyword_score, combined_score))
                    
                    scored_results.sort(key=lambda x: x[2], reverse=True)  # Sort by keyword_score
                    processed_results = [(chunk, vector_score, f"keyword_score={keyword_score:.1f}") 
                                       for chunk, vector_score, keyword_score, _ in scored_results[:request.top_k]]
                else:
                    processed_results = raw_search_results[:request.top_k]
                
                # Build processed chunks
                processed_chunks: List[dict] = []
                for rank, result in enumerate(processed_results, start=1):
                    if len(result) == 3:
                        chunk, score, match_type = result
                    else:
                        chunk, score = result
                        match_type = "vector_search"
                    
                    processed_chunks.append({
                        "chunk": chunk,
                        "score": round(score, 4),
                        "rank": rank,
                        "match_type": match_type,
                    })
                
                response_data["processed_results"] = processed_chunks
                response_data["keywords_extracted"] = keywords
                response_data["sku_extracted"] = extracted_sku
                logger.info(f"[RAG_DEBUG] ✓ Processed {len(processed_chunks)} results with business logic")
            except Exception as e:
                logger.warning(f"[RAG_DEBUG] Failed to generate processed results: {e}")
                response_data["processed_results_error"] = str(e)
        
        logger.info("[RAG_DEBUG] ========== Request Completed ==========")
        
        return RAGPreviewResponse(
            success=True,
            message="RAG preview completed successfully",
            data=response_data,
        )
        
    except Exception as e:
        logger.error(f"[RAG_DEBUG] ✗ Error during RAG preview: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to preview RAG results: {str(e)}",
        )


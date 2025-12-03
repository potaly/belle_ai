"""FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.api.v1 import (
    copy as copy_router,
    followup as followup_router,
    intent as intent_router,
    product as product_router,
    rag_debug as rag_debug_router,
    vector_search as vector_search_router,
)
from app.api.v1.router import router as v1_router
from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Smart Guide Service - Intelligent sales assistant for retail",
)

# Include routers
app.include_router(v1_router)
app.include_router(copy_router.router)
app.include_router(product_router.router)
app.include_router(vector_search_router.router)  # V2: 向量搜索API
app.include_router(rag_debug_router.router)  # V2: RAG 调试端点（仅 DEBUG 模式）
app.include_router(intent_router.router)  # V3: 意图分析API
app.include_router(followup_router.router)  # V3: 跟进建议API


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

"""FastAPI application entry point."""
import logging

from fastapi import FastAPI

from app.api.v1 import copy as copy_router, product as product_router
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

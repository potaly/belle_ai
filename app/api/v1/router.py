"""API v1 router with basic endpoints."""
from fastapi import APIRouter

from app.schemas.base_schemas import BaseResponse

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/ping", response_model=BaseResponse[str])
async def ping() -> BaseResponse[str]:
    """
    Health check endpoint.
    
    Returns:
        BaseResponse with "pong" message
    """
    return BaseResponse(data="pong", message="Service is running")


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint for API v1."""
    return {"version": "1.0.0", "status": "ok"}


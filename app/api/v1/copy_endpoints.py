from fastapi import APIRouter

from app.models.copy_schemas import CopyRequest, CopyResponse
from app.services.copy_service import generate_copy

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/generate/copy", response_model=CopyResponse)
async def create_copy(payload: CopyRequest) -> CopyResponse:
    
    return generate_copy(payload)
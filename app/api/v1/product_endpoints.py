from fastapi import APIRouter

from app.models.product_schemas import (
    ProductAnalysisRequest,
    ProductAnalysisResponse,
)
from app.services.product_service import analyze_product

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/analyze/product", response_model=ProductAnalysisResponse)
async def analyze_product_api(payload: ProductAnalysisRequest) -> ProductAnalysisResponse:
    return analyze_product(payload)
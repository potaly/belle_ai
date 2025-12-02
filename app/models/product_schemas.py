from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class ProductAttributes(BaseModel):
    color: Optional[str] = None
    material: Optional[str] = None
    scene: Optional[str] = None
    season: Optional[str] = None


class ProductAnalysisRequest(BaseModel):
    sku: str = Field(..., description="SKU identifier")
    product_name: Optional[str] = None
    tags: Optional[List[str]] = None
    attributes: Optional[ProductAttributes] = None
    description: Optional[str] = None


class ProductAnalysisResponse(BaseModel):
    core_selling_points: List[str] = Field(default_factory=list)
    style_tags: List[str] = Field(default_factory=list)
    scene_suggestion: List[str] = Field(default_factory=list)
    suitable_people: List[str] = Field(default_factory=list)
    pain_points_solved: List[str] = Field(default_factory=list)
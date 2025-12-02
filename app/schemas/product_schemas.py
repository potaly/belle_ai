"""Product analysis request and response schemas."""
from typing import List

from pydantic import BaseModel, Field


class ProductAnalysisRequest(BaseModel):
    """Request schema for product analysis."""

    sku: str = Field(..., description="Product SKU identifier")


class ProductAnalysisResponse(BaseModel):
    """Response schema for product analysis."""

    core_selling_points: List[str] = Field(
        default_factory=list,
        description="Core selling points of the product",
    )
    style_tags: List[str] = Field(
        default_factory=list,
        description="Style tags for the product",
    )
    scene_suggestion: List[str] = Field(
        default_factory=list,
        description="Suggested usage scenes",
    )
    suitable_people: List[str] = Field(
        default_factory=list,
        description="Suitable target audience",
    )
    pain_points_solved: List[str] = Field(
        default_factory=list,
        description="Pain points that the product solves",
    )


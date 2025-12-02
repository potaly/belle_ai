"""Copy generation request and response schemas."""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CopyStyle(str, Enum):
    """Copy writing style options."""

    natural = "natural"
    professional = "professional"
    funny = "funny"


class CopyRequest(BaseModel):
    """Request schema for copy generation."""

    sku: str = Field(..., description="SKU identifier")
    product_name: Optional[str] = Field(None, description="Display name")
    tags: Optional[List[str]] = Field(default=None, description="Optional product tags")
    style: CopyStyle = Field(default=CopyStyle.natural, description="Desired tone")


class CopyResponse(BaseModel):
    """Response schema for copy generation."""

    posts: List[str] = Field(default_factory=list, description="Candidate posts")


from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class CopyStyle(str, Enum):
    natural = "natural"
    professional = "professional"
    funny = "funny"


class CopyRequest(BaseModel):
    sku: str = Field(..., description="SKU identifier")
    product_name: Optional[str] = Field(None, description="Display name")
    tags: Optional[List[str]] = Field(default=None, description="Optional product tags")
    style: CopyStyle = Field(default=CopyStyle.natural, description="Desired tone")


class CopyResponse(BaseModel):
    posts: List[str] = Field(default_factory=list, description="Candidate posts")
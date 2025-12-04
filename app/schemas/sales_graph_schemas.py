"""Sales graph API request and response schemas."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class SalesGraphRequest(BaseModel):
    """Request schema for sales graph execution."""

    user_id: str = Field(..., description="User ID")
    sku: str = Field(..., description="Product SKU")
    guide_id: Optional[str] = Field(None, description="Guide ID (optional)")
    use_custom_plan: bool = Field(
        False,
        description="Whether to use planner to generate custom plan (if False, use full graph flow)",
    )


class SalesGraphResponse(BaseModel):
    """Response schema for sales graph execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    message: str = Field(..., description="Response message")
    data: Optional[dict[str, Any]] = Field(None, description="Response data")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Sales graph executed successfully",
                "data": {
                    "user_id": "user_001",
                    "sku": "8WZ01CM1",
                    "intent_level": "high",
                    "allowed": True,
                    "messages_count": 2,
                    "rag_chunks_count": 3,
                    "plan_used": ["fetch_product", "fetch_behavior_summary", "classify_intent", "anti_disturb_check", "retrieve_rag", "generate_copy"],
                    "final_message": "这是一款舒适的跑鞋...",
                },
            },
        }


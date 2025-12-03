"""Follow-up suggestion request and response schemas."""
from __future__ import annotations

from typing import Dict, Optional

from pydantic import BaseModel, Field

from app.schemas.base_schemas import BaseResponse


class FollowupRequest(BaseModel):
    """Request schema for follow-up suggestion."""

    user_id: str = Field(..., description="User ID", min_length=1)
    sku: str = Field(..., description="Product SKU identifier", min_length=1)
    limit: int = Field(50, description="Maximum number of behavior logs to analyze", ge=1, le=100)


class FollowupResponseData(BaseModel):
    """Data model for follow-up suggestion response."""

    user_id: str = Field(..., description="User ID")
    sku: str = Field(..., description="Product SKU")
    product_name: str = Field(..., description="Product name")
    intention_level: str = Field(
        ...,
        description="Intent level: high, medium, low, or hesitating",
        pattern="^(high|medium|low|hesitating)$",
    )
    suggested_action: str = Field(
        ...,
        description="Suggested action type (e.g., ask_size, send_coupon, explain_benefits, passive_message)",
    )
    message: str = Field(..., description="Personalized follow-up message")
    behavior_summary: Optional[Dict] = Field(
        None,
        description="Summary of user behavior data used for analysis",
    )
    total_logs_analyzed: int = Field(
        0,
        description="Total number of behavior logs analyzed",
    )


class FollowupResponse(BaseResponse[FollowupResponseData]):
    """Response model for follow-up suggestion endpoint."""

    pass


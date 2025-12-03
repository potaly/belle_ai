"""Intent analysis request and response schemas."""
from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class IntentAnalysisRequest(BaseModel):
    """Request schema for intent analysis."""

    user_id: str = Field(..., description="User ID", min_length=1)
    sku: str = Field(..., description="Product SKU identifier", min_length=1)
    limit: int = Field(50, description="Maximum number of behavior logs to analyze", ge=1, le=100)


class BehaviorSummary(BaseModel):
    """Behavior summary data."""

    visit_count: int = Field(..., description="Number of visits")
    max_stay_seconds: int = Field(..., description="Maximum stay time in seconds")
    avg_stay_seconds: float = Field(..., description="Average stay time in seconds")
    total_stay_seconds: int = Field(..., description="Total stay time across all visits")
    has_enter_buy_page: bool = Field(..., description="Whether user entered buy page")
    has_favorite: bool = Field(..., description="Whether user favorited the product")
    has_share: bool = Field(..., description="Whether user shared the product")
    has_click_size_chart: bool = Field(..., description="Whether user clicked size chart")
    event_types: List[str] = Field(..., description="List of event types occurred")
    event_type_counts: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of each event type",
    )


class IntentAnalysisResponse(BaseModel):
    """Response schema for intent analysis."""

    user_id: str = Field(..., description="User ID")
    sku: str = Field(..., description="Product SKU")
    intent_level: str = Field(
        ...,
        description="Intent level: high, medium, low, or hesitating",
        pattern="^(high|medium|low|hesitating)$",
    )
    reason: str = Field(..., description="Textual explanation of the intent level")
    behavior_summary: Optional[BehaviorSummary] = Field(
        None,
        description="Summary of user behavior data used for analysis",
    )
    total_logs_analyzed: int = Field(
        0,
        description="Total number of behavior logs analyzed",
    )


"""Agent sales flow API request and response schemas."""
from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, Field


class AgentSalesFlowRequest(BaseModel):
    """Request schema for agent sales flow execution."""

    user_id: str = Field(..., description="User ID")
    guide_id: Optional[str] = Field(None, description="Guide ID (optional)")
    sku: str = Field(..., description="Product SKU")

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_001",
                "guide_id": "guide_001",
                "sku": "8WZ01CM1",
            },
        }


class MessageItem(BaseModel):
    """Message item in response."""

    role: str = Field(..., description="Message role: system, user, or assistant")
    content: str = Field(..., description="Message content")


class AgentSalesFlowResponse(BaseModel):
    """Response schema for agent sales flow execution."""

    success: bool = Field(..., description="Whether execution succeeded")
    message: str = Field(..., description="Response message")
    data: Optional[dict[str, Any]] = Field(None, description="Response data")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Agent sales flow executed successfully",
                "data": {
                    "user_id": "user_001",
                    "guide_id": "guide_001",
                    "sku": "8WZ01CM1",
                    "product": {
                        "name": "跑鞋女2024新款舒适",
                        "price": 398.0,
                        "tags": ["舒适", "轻便", "透气"],
                    },
                    "behavior_summary": {
                        "visit_count": 2,
                        "max_stay_seconds": 25,
                        "avg_stay_seconds": 20.0,
                        "has_enter_buy_page": True,
                        "has_favorite": False,
                    },
                    "intent": {
                        "level": "high",
                        "reason": "用户已进入购买页面，这是强烈的购买信号。",
                    },
                    "allowed": True,
                    "anti_disturb_blocked": False,
                    "rag_used": True,
                    "rag_chunks_count": 3,
                    "messages": [
                        {
                            "role": "assistant",
                            "content": "这是一款舒适的跑鞋，采用网面材质，透气轻便...",
                        },
                    ],
                    "plan_executed": [
                        "fetch_product",
                        "fetch_behavior_summary",
                        "classify_intent",
                        "anti_disturb_check",
                        "retrieve_rag",
                        "generate_copy",
                    ],
                },
            },
        }


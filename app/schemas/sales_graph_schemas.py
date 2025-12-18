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


class MessageItemSchema(BaseModel):
    """Message item in message pack."""

    type: str = Field(..., description="Message type: 'primary' or 'alternative'")
    strategy: str = Field(..., description="Strategy description")
    message: str = Field(..., description="Message content")


class FollowupPlaybookItemSchema(BaseModel):
    """Follow-up playbook item for guides (V5.8.0+)."""

    condition: str = Field(..., description="Customer response condition (e.g., '顾客说尺码不确定')")
    reply: str = Field(..., description="Suggested reply message")


class SendRecommendationSchema(BaseModel):
    """Send recommendation with risk assessment (V5.6.0+)."""

    suggested: bool = Field(..., description="Whether to send")
    best_timing: str = Field(..., description="Best timing: 'now', 'within 30 minutes', 'tonight 19-21', etc.")
    note: str = Field(..., description="Short operational note")
    risk_level: str = Field(..., description="Risk level: 'low', 'medium', or 'high'")
    next_step: str = Field(..., description="What the guide should do after customer replies")


class SalesSuggestionSchema(BaseModel):
    """Sales suggestion pack for store guides (V5.4.0+)."""

    intent_level: str = Field(..., description="Intent level: high/hesitating/medium/low")
    confidence: str = Field(..., description="Confidence level: high/medium/low")
    why_now: str = Field(..., description="Human readable explanation for timing")
    recommended_action: str = Field(..., description="Recommended action type")
    action_explanation: str = Field(..., description="Explanation of recommended action")
    message_pack: List[MessageItemSchema] = Field(..., description="3+ candidate messages with different strategies (V5.6.0+)")
    send_recommendation: SendRecommendationSchema = Field(..., description="Send recommendation")
    followup_playbook: List[FollowupPlaybookItemSchema] = Field(
        default_factory=list,
        description="Follow-up playbook for guides (V5.8.0+ - only for high/hesitating intent)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "intent_level": "high",
                "confidence": "high",
                "why_now": "用户已访问 3 次，表现出持续关注；用户已收藏商品",
                "recommended_action": "ask_size",
                "action_explanation": "用户已查看尺码表，建议主动询问尺码以推进购买",
                "message_pack": [
                    {
                        "type": "primary",
                        "strategy": "询问尺码",
                        "message": "我看你刚进到购买页了～你平时穿多少码？我帮你对一下更稳～",
                    },
                    {
                        "type": "alternative",
                        "strategy": "场景推荐",
                        "message": "这款很多人通勤穿，你平时上班穿得多吗？我给你简单说下特点～",
                    },
                    {
                        "type": "alternative",
                        "strategy": "舒适度保证",
                        "message": "这款舒适，穿着很舒服，你平时穿鞋在意脚感吗？",
                    },
                ],
                "send_recommendation": {
                    "suggested": True,
                    "best_timing": "now",
                    "note": "用户购买意图明确，建议主动联系",
                    "risk_level": "low",
                    "next_step": "根据用户回复的尺码，推荐合适款式",
                },
                "followup_playbook": [
                    {
                        "condition": "顾客说尺码不确定",
                        "reply": "你平时这类鞋穿多少码？脚背高不高？我帮你更准一点～",
                    },
                    {
                        "condition": "顾客说再看看",
                        "reply": "好的不急～你如果在意脚感或搭配，我也可以给你更具体的建议～",
                    },
                ],
            },
        }


class SalesGraphResponse(BaseModel):
    # 响应销售流程图执行的响应模型
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
                    "rag_used": True,
                    "rag_chunks_count": 3,
                    "rag_chunks": [
                        "这是一款专为跑步设计的舒适跑鞋，采用透气网面材质...",
                        "鞋底采用缓震科技，有效减少跑步时的冲击力...",
                        "适合日常跑步和长距离训练，深受跑者喜爱..."
                    ],
                    "rag_diagnostics": {
                        "retrieved_count": 6,
                        "filtered_count": 3,
                        "safe_count": 3,
                        "filter_reasons": [
                            "Chunk contains foreign SKU(s): 8WZ76CM6 (prevent cross-SKU contamination)"
                        ]
                    },
                    "plan_used": ["fetch_product", "fetch_behavior_summary", "classify_intent", "anti_disturb_check", "retrieve_rag", "generate_copy"],
                    "decision_reason": "用户意图级别为 high：用户已进入购买页面，这是强烈的购买信号。；反打扰检查通过，允许主动接触",
                    "final_message": "这是一款舒适的跑鞋...",
                },
            },
        }


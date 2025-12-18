"""Copy generation request and response schemas (V5.5.0+).

商品维度话术生成接口（无用户）：
- 输入：SKU + scene 参数
- 输出：商品卖点 + 多条话术候选
- 不涉及用户行为、意图分析、销售决策
"""
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class CopyStyle(str, Enum):
    """Copy writing style options (backward compatible)."""

    natural = "natural"
    professional = "professional"
    funny = "funny"  # Legacy, mapped to "friendly" in V5.5.0+


class CopyScene(str, Enum):
    """Copy target scene (V5.5.0+)."""

    guide_chat = "guide_chat"  # 导购私聊
    moments = "moments"  # 朋友圈
    poster = "poster"  # 海报


class CopyUseCase(str, Enum):
    """Copy use case (V5.5.0+)."""

    product_only = "product_only"  # 纯商品话术（默认）
    marketing = "marketing"  # 营销场景（向后兼容）


class CopyRequest(BaseModel):
    """Request schema for copy generation (V5.5.0+ - backward compatible)."""

    sku: str = Field(..., description="SKU identifier")
    product_name: Optional[str] = Field(
        None, description="Display name (optional, will be loaded from DB)"
    )
    tags: Optional[List[str]] = Field(
        default=None, description="Optional product tags (will be loaded from DB)"
    )
    style: CopyStyle = Field(
        default=CopyStyle.natural,
        description="Desired tone (natural/professional/funny - backward compatible)",
    )
    scene: Optional[CopyScene] = Field(
        default=CopyScene.guide_chat,
        description="Target scene: guide_chat/moments/poster (V5.5.0+)",
    )
    use_case: Optional[CopyUseCase] = Field(
        default=CopyUseCase.product_only,
        description="Use case: product_only/marketing (V5.5.0+)",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sku": "8WZ01CM1",
                "scene": "guide_chat",
                "style": "natural",
                "use_case": "product_only",
            },
        }


class CopyCandidateSchema(BaseModel):
    """Copy candidate with scene and style."""

    scene: str = Field(..., description="Target scene")
    style: str = Field(..., description="Writing style")
    message: str = Field(..., description="Generated copy message")


class CopyResponse(BaseModel):
    """Response schema for copy generation (V5.5.0+ - backward compatible)."""

    sku: str = Field(..., description="Product SKU")
    product_name: str = Field(..., description="Product name")
    selling_points: List[str] = Field(..., description="Product selling points (3-5 items)")
    copy_candidates: List[CopyCandidateSchema] = Field(
        ..., description="Copy candidates (2-3 items)"
    )
    # Backward compatible field
    posts: Optional[List[str]] = Field(
        default=None, description="Legacy field: list of copy messages (for old clients)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "sku": "8WZ01CM1",
                "product_name": "舒适运动鞋",
                "selling_points": [
                    "舒适脚感，久走不累",
                    "透气材质，保持干爽",
                    "百搭款式，轻松搭配",
                ],
                "copy_candidates": [
                    {
                        "scene": "guide_chat",
                        "style": "natural",
                        "message": "这款黑色运动鞋很舒适，适合日常运动",
                    },
                    {
                        "scene": "guide_chat",
                        "style": "natural",
                        "message": "黑色运动鞋，透气轻便，百搭实用",
                    },
                ],
                "posts": [
                    "这款黑色运动鞋很舒适，适合日常运动",
                    "黑色运动鞋，透气轻便，百搭实用",
                ],
            },
        }


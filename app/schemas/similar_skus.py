"""Similar SKUs search API schemas (V6.0.0+)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class VisionFeatures(BaseModel):
    """Vision features from Step 1."""

    category: Optional[str] = Field(None, description="商品类型（如：运动鞋/休闲鞋）")
    style: Optional[List[str]] = Field(
        default_factory=list,
        description="风格（如：['休闲', '日常']）",
    )
    color: Optional[str] = Field(None, description="颜色（如：黑色）")
    season: Optional[str] = Field(None, description="季节（如：四季）")
    keywords: Optional[List[str]] = Field(
        default_factory=list,
        description="关键词（如：['百搭', '轻便']）",
    )


class SimilarSKUsRequest(BaseModel):
    """Similar SKUs search request schema."""

    brand_code: str = Field(..., description="品牌编码", examples=["BL"])
    top_k: int = Field(
        default=5,
        ge=1,
        le=5,
        description="返回结果数量（最多5个）",
    )
    vision_features: Optional[VisionFeatures] = Field(
        None, description="视觉特征（来自Step 1，与 trace_id 二选一）"
    )
    trace_id: Optional[str] = Field(
        None, description="追踪ID（来自Step 1，与 vision_features 二选一）"
    )
    mode: str = Field(
        default="rule",
        description="检索模式：rule（规则检索）或 vector（向量检索）",
    )

    @model_validator(mode="after")
    def validate_inputs(self) -> "SimilarSKUsRequest":
        """验证 vision_features 和 trace_id 至少提供一个。"""
        if not self.vision_features and not self.trace_id:
            raise ValueError("vision_features 和 trace_id 至少需要提供一个")
        if self.vision_features and self.trace_id:
            raise ValueError("vision_features 和 trace_id 不能同时提供")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "brand_code": "BL",
                "top_k": 5,
                "vision_features": {
                    "category": "运动鞋",
                    "style": ["休闲", "日常"],
                    "color": "黑色",
                    "season": "四季",
                    "keywords": ["百搭", "轻便"],
                },
                "mode": "rule",
            }
        }


class SimilarSKUsResponse(BaseModel):
    """Similar SKUs search response schema."""

    success: bool = Field(..., description="是否成功")
    data: Optional[dict] = Field(None, description="结果数据")
    message: Optional[str] = Field(None, description="错误消息（失败时）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "similar_skus": ["8WZ01CM1", "8WZ21CM1", "8WZ81CM1", "8WZ71CM1", "8WZ51CM1"],
                },
            }
        }


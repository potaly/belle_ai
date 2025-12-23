"""Vision analysis API schemas (V6.0.0+)."""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator


class VisionAnalyzeRequest(BaseModel):
    """Vision analysis request schema."""

    image: str = Field(
        ...,
        description="商品图片URL或Base64编码",
        examples=["https://example.com/product.jpg"],
    )
    brand_code: str = Field(
        ...,
        description="品牌编码",
        examples=["BELLE"],
    )
    scene: str = Field(
        default="guide_chat",
        description="使用场景（固定为guide_chat）",
    )

    @model_validator(mode="after")
    def validate_scene(self):
        """验证 scene 必须为 guide_chat。"""
        if self.scene != "guide_chat":
            raise ValueError("scene 必须为 'guide_chat'")
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "image": "https://example.com/product.jpg",
                "brand_code": "BELLE",
                "scene": "guide_chat",
            }
        }


class VisualSummary(BaseModel):
    """Visual summary schema."""

    category_guess: str = Field(..., description="商品类型猜测（如：运动鞋/休闲鞋）")
    style_impression: List[str] = Field(
        default_factory=list,
        description="风格印象（如：['休闲', '日常']）",
    )
    color_impression: str = Field(..., description="颜色印象（如：黑色）")
    season_impression: str = Field(..., description="季节印象（如：四季）")
    confidence_note: str = Field(
        default="基于图片外观判断，可能存在误差",
        description="置信度说明",
    )


class GuideChatCopy(BaseModel):
    """Guide chat copy schema."""

    primary: str = Field(..., description="主要话术（必须包含轻提问式引导）")
    alternatives: List[str] = Field(
        default_factory=list,
        description="备选话术（至少3条）",
        min_length=3,
    )


class Tracking(BaseModel):
    """Tracking information schema."""

    vision_used: bool = Field(..., description="是否使用了视觉模型")
    confidence_level: str = Field(..., description="置信度级别（high/medium/low）")


class VisionAnalyzeData(BaseModel):
    """Vision analysis data schema."""

    visual_summary: VisualSummary = Field(..., description="视觉摘要")
    selling_points: List[str] = Field(
        default_factory=list,
        description="卖点（基于外观，不编造材质/功能）",
    )
    guide_chat_copy: GuideChatCopy = Field(..., description="导购私聊话术")
    tracking: Tracking = Field(..., description="追踪信息")


class VisionAnalyzeResponse(BaseModel):
    """Vision analysis response schema."""

    success: bool = Field(..., description="是否成功")
    data: Optional[VisionAnalyzeData] = Field(None, description="分析结果数据")
    message: Optional[str] = Field(None, description="错误消息（失败时）")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {
                    "visual_summary": {
                        "category_guess": "运动鞋",
                        "style_impression": ["休闲", "日常"],
                        "color_impression": "黑色",
                        "season_impression": "四季",
                        "confidence_note": "基于图片外观判断，可能存在误差",
                    },
                    "selling_points": [
                        "外观看起来比较百搭",
                        "整体感觉偏轻便，适合日常穿",
                        "风格偏休闲，通勤或周末都合适",
                    ],
                    "guide_chat_copy": {
                        "primary": "这双看起来比较百搭，平时走路多还是通勤穿得多一些？",
                        "alternatives": [
                            "这款整体偏日常，穿着不会太累脚，你平时穿运动鞋多吗？",
                            "这双风格比较休闲，搭牛仔裤也挺合适的",
                            "从外观看感觉比较轻便，你平时更看重舒适度还是搭配？",
                        ],
                    },
                    "tracking": {
                        "vision_used": True,
                        "confidence_level": "medium",
                    },
                },
            }
        }


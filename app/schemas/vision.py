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


class StructureSignals(BaseModel):
    """Structure signals schema (P4.x.1)."""

    open_heel: bool = Field(default=False, description="是否后空")
    open_toe: bool = Field(default=False, description="是否前空")
    heel_height: str = Field(
        default="unknown",
        description="跟高（flat/low/mid/high/unknown）",
    )
    toe_shape: str = Field(
        default="unknown",
        description="鞋头形状（round/square/pointed/unknown）",
    )


class ResolverDebug(BaseModel):
    """Resolver debug information schema (P4.x.1)."""

    brand_no: str = Field(..., description="品牌编码")
    allowed_categories_count: int = Field(0, description="允许的类目数量")
    allowed_styles_count: int = Field(0, description="允许的风格数量")
    allowed_seasons_count: int = Field(0, description="允许的季节数量")
    allowed_colors_count: int = Field(0, description="允许的颜色数量")
    strategy_used: str = Field(
        default="llm_enum",
        description="使用的策略（llm_enum/fallback_rule）",
    )
    corrections: List[str] = Field(
        default_factory=list,
        description="修正记录（如：['open_heel=>后空凉鞋', 'category_not_allowed=>UNKNOWN']）",
    )


class VisualSummary(BaseModel):
    """Visual summary schema."""

    category_guess_raw: Optional[str] = Field(
        None, description="原始 category（VLM 输出）"
    )
    category_guess: str = Field(..., description="归一化后的商品类型（如：运动鞋/休闲鞋）")
    style_impression_raw: Optional[List[str]] = Field(
        None, description="原始 style（VLM 输出）"
    )
    style_impression: List[str] = Field(
        default_factory=list,
        description="归一化后的风格印象（如：['休闲', '日常']）",
    )
    color_impression_raw: Optional[str] = Field(None, description="原始 color（VLM 输出）")
    color_impression: str = Field(..., description="归一化后的颜色印象（如：黑色）")
    season_impression_raw: Optional[str] = Field(None, description="原始 season（VLM 输出）")
    season_impression: str = Field(..., description="归一化后的季节印象（如：四季）")
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


class VisionFeatures(BaseModel):
    """Normalized vision features schema (for retrieval)."""

    category: Optional[str] = Field(None, description="商品类型（归一化后）")
    style: List[str] = Field(
        default_factory=list,
        description="风格（归一化后，最多5个）",
    )
    color: Optional[str] = Field(None, description="主色（归一化后）")
    colors: List[str] = Field(
        default_factory=list,
        description="颜色列表（归一化后，去重）",
    )
    season: str = Field(default="四季", description="季节（归一化后）")
    scene: str = Field(default="guide_chat", description="使用场景")
    keywords: List[str] = Field(
        default_factory=list,
        description="关键词（3~6个）",
    )


class VisionAnalyzeData(BaseModel):
    """Vision analysis data schema."""

    visual_summary: VisualSummary = Field(..., description="视觉摘要")
    structure_signals: Optional[StructureSignals] = Field(
        None, description="结构特征（P4.x.1）"
    )
    selling_points: List[str] = Field(
        default_factory=list,
        description="卖点（基于外观，不编造材质/功能）",
    )
    guide_chat_copy: GuideChatCopy = Field(..., description="导购私聊话术")
    tracking: Tracking = Field(..., description="追踪信息")
    trace_id: Optional[str] = Field(None, description="追踪ID（用于串联Step2）")
    vision_features: Optional[VisionFeatures] = Field(
        None, description="归一化后的视觉特征（用于检索）"
    )
    resolver_debug: Optional[ResolverDebug] = Field(
        None, description="解析器调试信息（P4.x.1）"
    )


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


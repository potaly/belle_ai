"""Tests for vision enum resolver (P4.x.1)."""
from __future__ import annotations

import pytest
from app.services.vision_enum_resolver import VisionEnumResolver


class TestVisionEnumResolver:
    """Test vision enum resolver with fallback rules."""

    def test_resolve_with_fallback_open_heel(self):
        """测试 open_heel 规则兜底：category="单鞋" + open_heel=true => "后空凉鞋"。"""
        vlm_output = {
            "category": "单鞋",
            "season": "四季",
            "style": ["优雅"],
            "color": "黑色",
            "colors": ["黑色"],
            "structure_signals": {
                "open_heel": True,
                "open_toe": False,
                "heel_height": "mid",
                "toe_shape": "round",
            },
            "selling_points": ["外观优雅"],
            "guide_chat_copy": {
                "primary": "这双看起来不错，你平时穿什么码？",
                "alternatives": ["备选1", "备选2", "备选3"],
            },
            "confidence": "medium",
        }

        allowed_enums = {
            "categories": ["后空凉鞋", "中空凉鞋", "纯凉鞋", "运动鞋"],
            "seasons": ["夏季", "秋季", "冬季"],
            "styles": ["优雅", "休闲", "时尚"],
            "colors": ["黑色", "白色", "红色"],
        }

        resolved, corrections = VisionEnumResolver.resolve_with_fallback(
            vlm_output=vlm_output,
            allowed_enums=allowed_enums,
            brand_no="TEST_BRAND",
        )

        # 断言：category 应该被修正为 "后空凉鞋"
        assert resolved["category"] == "后空凉鞋"
        assert resolved["category_guess"] == "后空凉鞋"
        assert "open_heel=>后空凉鞋" in corrections

    def test_resolve_with_fallback_open_toe(self):
        """测试 open_toe 规则兜底：category="单鞋" + open_toe=true => "纯凉鞋"。"""
        vlm_output = {
            "category": "单鞋",
            "season": "四季",
            "style": ["休闲"],
            "color": "白色",
            "colors": ["白色"],
            "structure_signals": {
                "open_heel": False,
                "open_toe": True,
                "heel_height": "flat",
                "toe_shape": "round",
            },
        }

        allowed_enums = {
            "categories": ["后空凉鞋", "中空凉鞋", "纯凉鞋", "运动鞋"],
            "seasons": ["夏季", "秋季"],
            "styles": ["休闲"],
            "colors": ["白色"],
        }

        resolved, corrections = VisionEnumResolver.resolve_with_fallback(
            vlm_output=vlm_output,
            allowed_enums=allowed_enums,
            brand_no="TEST_BRAND",
        )

        assert resolved["category"] == "纯凉鞋"
        assert "open_toe=>纯凉鞋" in corrections

    def test_resolve_with_fallback_category_not_allowed(self):
        """测试 category 不在 allowed 列表中的兜底。"""
        vlm_output = {
            "category": "单鞋",
            "season": "四季",
            "style": [],
            "color": "黑色",
            "colors": ["黑色"],
            "structure_signals": {
                "open_heel": False,
                "open_toe": False,
            },
        }

        allowed_enums = {
            "categories": ["后空凉鞋", "运动鞋"],
            "seasons": ["夏季"],
            "styles": [],
            "colors": ["黑色"],
        }

        resolved, corrections = VisionEnumResolver.resolve_with_fallback(
            vlm_output=vlm_output,
            allowed_enums=allowed_enums,
            brand_no="TEST_BRAND",
        )

        # 应该选择第一个 allowed category
        assert resolved["category"] == "后空凉鞋"
        assert "category_not_allowed=>后空凉鞋" in corrections

    def test_resolve_with_fallback_season_inference(self):
        """测试 season 根据 category 推断：category="后空凉鞋" => season="夏季"。"""
        vlm_output = {
            "category": "后空凉鞋",
            "season": "四季",  # 不在 allowed_seasons 中
            "style": [],
            "color": "黑色",
            "colors": ["黑色"],
            "structure_signals": {
                "open_heel": True,
            },
        }

        allowed_enums = {
            "categories": ["后空凉鞋"],
            "seasons": ["夏季", "秋季"],
            "styles": [],
            "colors": ["黑色"],
        }

        resolved, corrections = VisionEnumResolver.resolve_with_fallback(
            vlm_output=vlm_output,
            allowed_enums=allowed_enums,
            brand_no="TEST_BRAND",
        )

        assert resolved["season"] == "夏季"
        assert "category_infers_season=>夏季" in corrections

    def test_resolve_with_fallback_style_filter(self):
        """测试 style 过滤：只保留在 allowed_styles 中的。"""
        vlm_output = {
            "category": "运动鞋",
            "season": "四季",
            "style": ["优雅", "休闲", "未知风格"],  # "未知风格" 不在 allowed 中
            "color": "黑色",
            "colors": ["黑色"],
            "structure_signals": {},
        }

        allowed_enums = {
            "categories": ["运动鞋"],
            "seasons": ["四季"],
            "styles": ["优雅", "休闲", "时尚"],
            "colors": ["黑色"],
        }

        resolved, corrections = VisionEnumResolver.resolve_with_fallback(
            vlm_output=vlm_output,
            allowed_enums=allowed_enums,
            brand_no="TEST_BRAND",
        )

        assert "优雅" in resolved["style"]
        assert "休闲" in resolved["style"]
        assert "未知风格" not in resolved["style"]
        assert len(resolved["style"]) <= 3


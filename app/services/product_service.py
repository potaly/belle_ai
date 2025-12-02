"""Service for product analysis using rule-based logic."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.models.product import Product
from app.schemas.product_schemas import ProductAnalysisResponse

logger = logging.getLogger(__name__)


def analyze_product(product: Product) -> ProductAnalysisResponse:
    """
    Analyze product using rule-based logic.
    
    Derives analysis fields from product.tags and product.attributes.
    
    Args:
        product: Product instance from database
        
    Returns:
        ProductAnalysisResponse with analyzed data
    """
    logger.info(f"[SERVICE] ========== Product Analysis Service Started ==========")
    logger.info(f"[SERVICE] Input: sku={product.sku}, name={product.name}")
    logger.info(f"[SERVICE] Product tags: {product.tags}")
    logger.info(f"[SERVICE] Product attributes: {product.attributes}")
    
    # Extract tags and attributes
    tags: List[str] = product.tags or []
    attributes: Dict[str, Any] = product.attributes or {}
    
    logger.info(f"[SERVICE] Step 1: Extracted tags={tags}, attributes={attributes}")
    
    # Initialize result lists
    core_selling_points: List[str] = []
    style_tags: List[str] = []
    scene_suggestion: List[str] = []
    suitable_people: List[str] = []
    pain_points_solved: List[str] = []
    
    logger.info(f"[SERVICE] Step 2: Applying rule-based logic...")
    
    # Rule-based logic: derive fields from tags
    for tag in tags:
        tag_lower = tag.lower()
        
        # Core selling points rules
        if "百搭" in tag:
            core_selling_points.append("适配多场景穿搭")
            logger.debug(f"[SERVICE]   Rule: '百搭' -> added '适配多场景穿搭' to core_selling_points")
        
        if "舒适" in tag:
            core_selling_points.append("舒适包裹，久穿不累")
            logger.debug(f"[SERVICE]   Rule: '舒适' -> added '舒适包裹，久穿不累' to core_selling_points")
        
        if "时尚" in tag:
            core_selling_points.append("时尚设计，提升气质")
            logger.debug(f"[SERVICE]   Rule: '时尚' -> added '时尚设计，提升气质' to core_selling_points")
        
        if "轻便" in tag:
            core_selling_points.append("轻盈出行，减轻负担")
            logger.debug(f"[SERVICE]   Rule: '轻便' -> added '轻盈出行，减轻负担' to core_selling_points")
        
        if "透气" in tag:
            core_selling_points.append("透气排汗，保持干爽")
            logger.debug(f"[SERVICE]   Rule: '透气' -> added '透气排汗，保持干爽' to core_selling_points")
        
        if "防滑" in tag:
            core_selling_points.append("防滑设计，安全可靠")
            logger.debug(f"[SERVICE]   Rule: '防滑' -> added '防滑设计，安全可靠' to core_selling_points")
        
        if "增高" in tag:
            core_selling_points.append("增高设计，拉长腿部线条")
            logger.debug(f"[SERVICE]   Rule: '增高' -> added '增高设计，拉长腿部线条' to core_selling_points")
        
        # Style tags rules
        if "百搭" in tag:
            style_tags.append("百搭")
        if "简约" in tag or "经典" in tag:
            style_tags.append("简约")
        if "时尚" in tag or "潮流" in tag:
            style_tags.append("时尚")
        if "复古" in tag or "英伦" in tag:
            style_tags.append("复古")
        if "甜美" in tag:
            style_tags.append("甜美")
        if "商务" in tag:
            style_tags.append("商务")
        if "运动" in tag:
            style_tags.append("运动")
        if "休闲" in tag:
            style_tags.append("休闲")
        
        # Pain points solved rules
        if "软底" in tag or "舒适" in tag:
            pain_points_solved.append("久走不累")
            logger.debug(f"[SERVICE]   Rule: '软底/舒适' -> added '久走不累' to pain_points_solved")
        
        if "轻便" in tag:
            pain_points_solved.append("减轻脚部负担")
            logger.debug(f"[SERVICE]   Rule: '轻便' -> added '减轻脚部负担' to pain_points_solved")
        
        if "透气" in tag:
            pain_points_solved.append("解决闷脚问题")
            logger.debug(f"[SERVICE]   Rule: '透气' -> added '解决闷脚问题' to pain_points_solved")
        
        if "防滑" in tag:
            pain_points_solved.append("防止滑倒")
            logger.debug(f"[SERVICE]   Rule: '防滑' -> added '防止滑倒' to pain_points_solved")
        
        if "增高" in tag:
            pain_points_solved.append("显腿长")
            logger.debug(f"[SERVICE]   Rule: '增高' -> added '显腿长' to pain_points_solved")
    
    # Rule-based logic: derive fields from attributes
    if attributes:
        # Scene suggestion from attributes.scene
        scene = attributes.get("scene")
        if scene:
            scene_suggestion.append(scene)
            logger.debug(f"[SERVICE]   Rule: attributes.scene='{scene}' -> added to scene_suggestion")
        
        # Additional scene suggestions based on material
        material = attributes.get("material", "").lower()
        if "真皮" in material or "pu" in material:
            if "通勤" not in scene_suggestion:
                scene_suggestion.append("通勤")
            if "商务" not in scene_suggestion:
                scene_suggestion.append("商务")
        
        if "帆布" in material or "网面" in material:
            if "休闲" not in scene_suggestion:
                scene_suggestion.append("休闲")
            if "运动" not in scene_suggestion:
                scene_suggestion.append("运动")
        
        # Season-based scene suggestions
        season = attributes.get("season", "").lower()
        if "四季" in season:
            scene_suggestion.extend(["通勤", "逛街", "约会"])
        elif "春秋" in season:
            scene_suggestion.extend(["通勤", "逛街"])
        elif "夏季" in season:
            scene_suggestion.extend(["休闲", "度假"])
        elif "冬季" in season:
            scene_suggestion.extend(["通勤", "保暖"])
        
        # Suitable people based on scene and style
        if "通勤" in scene_suggestion or "商务" in scene_suggestion:
            suitable_people.append("上班族")
        if "运动" in scene_suggestion or "休闲" in scene_suggestion:
            suitable_people.append("学生")
        if "时尚" in style_tags or "甜美" in style_tags:
            suitable_people.append("年轻女性")
        if "商务" in style_tags:
            suitable_people.append("职场人士")
    
    # Default values if lists are empty
    if not core_selling_points:
        core_selling_points = ["舒适包裹", "轻盈出行", "百搭配色"]
        logger.info(f"[SERVICE]   Using default core_selling_points")
    
    if not style_tags:
        style_tags = tags[:3] if tags else ["简约", "通勤"]
        logger.info(f"[SERVICE]   Using default style_tags")
    
    if not scene_suggestion:
        scene_suggestion = ["通勤", "逛街"]
        logger.info(f"[SERVICE]   Using default scene_suggestion")
    
    if not suitable_people:
        suitable_people = ["上班族", "学生"]
        logger.info(f"[SERVICE]   Using default suitable_people")
    
    if not pain_points_solved:
        pain_points_solved = ["久走不累", "显脚瘦"]
        logger.info(f"[SERVICE]   Using default pain_points_solved")
    
    # Remove duplicates while preserving order
    core_selling_points = list(dict.fromkeys(core_selling_points))
    style_tags = list(dict.fromkeys(style_tags))
    scene_suggestion = list(dict.fromkeys(scene_suggestion))
    suitable_people = list(dict.fromkeys(suitable_people))
    pain_points_solved = list(dict.fromkeys(pain_points_solved))
    
    logger.info(f"[SERVICE] Step 3: Analysis results:")
    logger.info(f"[SERVICE]   core_selling_points: {core_selling_points}")
    logger.info(f"[SERVICE]   style_tags: {style_tags}")
    logger.info(f"[SERVICE]   scene_suggestion: {scene_suggestion}")
    logger.info(f"[SERVICE]   suitable_people: {suitable_people}")
    logger.info(f"[SERVICE]   pain_points_solved: {pain_points_solved}")
    
    result = ProductAnalysisResponse(
        core_selling_points=core_selling_points,
        style_tags=style_tags,
        scene_suggestion=scene_suggestion,
        suitable_people=suitable_people,
        pain_points_solved=pain_points_solved,
    )
    
    logger.info(f"[SERVICE] ✓ Product analysis completed")
    logger.info(f"[SERVICE] ========== Product Analysis Service Completed ==========")
    
    return result

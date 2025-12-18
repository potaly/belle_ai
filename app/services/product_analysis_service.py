"""Product analysis service for extracting selling points (V5.5.0+).

核心职责：
- 从商品数据中提取 3-5 个卖点
- 规则驱动 + LLM 辅助
- 输出结构化（字符串列表）
- 不涉及用户行为、意图分析
"""
from __future__ import annotations

import logging
from typing import List, Optional

from app.models.product import Product
from app.services.llm_client import LLMClientError, get_llm_client

logger = logging.getLogger(__name__)

# 禁止词汇（与销售话术一致）
FORBIDDEN_WORDS = [
    "太香了",
    "必入",
    "闭眼冲",
    "爆款",
    "秒杀",
    "神鞋",
]


def analyze_selling_points(
    product: Product,
    use_llm: bool = True,
) -> List[str]:
    """
    分析商品卖点（规则驱动 + LLM 辅助）。
    
    业务规则：
    - 提取 3-5 个核心卖点
    - 基于商品事实，不编造
    - 输出结构化，便于后续使用
    
    Args:
        product: Product instance
        use_llm: Whether to use LLM for enhancement (default: True)
    
    Returns:
        List of selling points (3-5 items)
    """
    logger.info(
        f"[ANALYSIS] Analyzing selling points: sku={product.sku}, "
        f"name={product.name}"
    )
    
    # Step 1: Rule-based extraction
    selling_points = _extract_selling_points_by_rules(product)
    logger.info(f"[ANALYSIS] Rule-based extraction: {len(selling_points)} points")
    
    # Step 2: LLM enhancement (optional)
    if use_llm and len(selling_points) < 5:
        try:
            llm_enhanced = _enhance_with_llm(product, selling_points)
            if llm_enhanced:
                selling_points = llm_enhanced
                logger.info(f"[ANALYSIS] LLM enhancement: {len(selling_points)} points")
        except Exception as e:
            logger.warning(f"[ANALYSIS] LLM enhancement failed: {e}, using rule-based only")
    
    # Step 3: Ensure 3-5 points
    if len(selling_points) < 3:
        # Fill with generic points
        selling_points.extend(_get_generic_selling_points(product))
        selling_points = selling_points[:5]
    
    # Remove duplicates while preserving order
    seen = set()
    unique_points = []
    for point in selling_points:
        if point not in seen:
            seen.add(point)
            unique_points.append(point)
    
    final_points = unique_points[:5]  # Max 5 points
    
    logger.info(f"[ANALYSIS] ✓ Final selling points: {len(final_points)} points")
    for i, point in enumerate(final_points, 1):
        logger.debug(f"[ANALYSIS]   {i}. {point}")
    
    return final_points


def _extract_selling_points_by_rules(product: Product) -> List[str]:
    """使用规则提取卖点。"""
    points = []
    
    # 从 tags 提取
    tags = product.tags or []
    tag_to_point = {
        "舒适": "舒适脚感，久走不累",
        "软底": "软底设计，缓震护脚",
        "轻便": "轻便透气，出行无负担",
        "百搭": "百搭款式，轻松搭配",
        "时尚": "时尚设计，彰显品味",
        "透气": "透气材质，保持干爽",
        "防滑": "防滑设计，安全可靠",
        "增高": "增高设计，拉长腿部线条",
        "显瘦": "显瘦设计，修饰脚型",
    }
    
    for tag in tags:
        if tag in tag_to_point:
            point = tag_to_point[tag]
            if point not in points:
                points.append(point)
    
    # 从 attributes 提取
    attributes = product.attributes or {}
    if attributes:
        color = attributes.get("color", "")
        material = attributes.get("material", "")
        scene = attributes.get("scene", "")
        
        if color:
            points.append(f"{color}配色，经典耐看")
        
        if material:
            if "真皮" in material or "牛皮" in material:
                points.append("真皮材质，质感上乘")
            elif "网面" in material or "透气" in material:
                points.append("透气材质，舒适清爽")
        
        if scene:
            points.append(f"适合{scene}场景，实用性强")
    
    # 从价格提取（如果有优势）
    if product.price:
        # 可以根据价格区间判断，这里简化处理
        if product.price < 300:
            points.append("性价比高，物超所值")
    
    return points


def _enhance_with_llm(product: Product, existing_points: List[str]) -> Optional[List[str]]:
    """使用 LLM 增强卖点提取。"""
    llm_client = get_llm_client()
    if not llm_client.settings.llm_api_key or not llm_client.settings.llm_base_url:
        return None
    
    # 构建提示词
    product_name = product.name
    tags = product.tags or []
    attributes = product.attributes or {}
    description = product.description or ""
    
    prompt_parts = []
    prompt_parts.append("## 商品信息：")
    prompt_parts.append(f"商品名称：{product_name}")
    if tags:
        prompt_parts.append(f"标签：{', '.join(tags)}")
    if attributes:
        for key, value in attributes.items():
            prompt_parts.append(f"{key}：{value}")
    if description:
        prompt_parts.append(f"描述：{description[:200]}")  # 限制长度
    prompt_parts.append("")
    
    prompt_parts.append("## 任务：")
    prompt_parts.append("请从以上商品信息中提取 3-5 个核心卖点。")
    prompt_parts.append("要求：")
    prompt_parts.append("1. 每个卖点一句话，简洁明了")
    prompt_parts.append("2. 基于商品事实，不编造")
    prompt_parts.append("3. 禁止使用营销词汇（太香了/必入/爆款等）")
    prompt_parts.append("4. 输出格式：每行一个卖点")
    prompt_parts.append("")
    
    if existing_points:
        prompt_parts.append(f"已有卖点：{', '.join(existing_points)}")
        prompt_parts.append("请在此基础上补充或优化，确保输出 3-5 个卖点。")
        prompt_parts.append("")
    
    prompt_parts.append("只输出卖点内容，不要其他说明：")
    
    prompt = "\n".join(prompt_parts)
    
    try:
        response = llm_client.generate(
            prompt,
            system="你是一个专业的商品分析助手，擅长提取商品核心卖点。",
            temperature=0.7,
            max_tokens=200,
        )
        
        # 解析响应
        points = []
        for line in response.strip().split("\n"):
            line = line.strip()
            # 移除编号前缀（如"1. "、"第一条："等）
            if line.startswith(("1.", "2.", "3.", "4.", "5.", "第一条：", "第二条：")):
                line = line.split("：", 1)[-1].strip()
                if line.startswith(("1.", "2.", "3.", "4.", "5.")):
                    line = line.split(".", 1)[-1].strip()
            
            if line and len(line) > 3:  # 至少 3 个字符
                # 检查禁止词汇
                if not any(word in line for word in FORBIDDEN_WORDS):
                    points.append(line)
        
        # 合并现有卖点
        if existing_points:
            all_points = existing_points + points
        else:
            all_points = points
        
        # 去重并限制数量
        seen = set()
        unique_points = []
        for point in all_points:
            if point not in seen:
                seen.add(point)
                unique_points.append(point)
        
        return unique_points[:5]
        
    except LLMClientError as e:
        logger.warning(f"[ANALYSIS] LLM error: {e}")
        return None
    except Exception as e:
        logger.error(f"[ANALYSIS] Unexpected error in LLM enhancement: {e}", exc_info=True)
        return None


def _get_generic_selling_points(product: Product) -> List[str]:
    """获取通用卖点（当规则提取不足时使用）。"""
    points = []
    
    product_name = product.name
    if "运动" in product_name or "跑" in product_name:
        points.append("适合运动场景，舒适实用")
    elif "休闲" in product_name or "日常" in product_name:
        points.append("适合日常穿着，轻松舒适")
    else:
        points.append("经典款式，实用百搭")
    
    if product.price and product.price < 500:
        points.append("价格实惠，性价比高")
    
    points.append("品质保证，值得信赖")
    
    return points


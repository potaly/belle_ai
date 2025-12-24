"""Similar SKUs search service (V6.0.0+).

支持两种检索模式：
- rule: 规则检索 + 打分排序
- vector: 向量检索（异常时降级到 rule）
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.product import Product
from app.repositories.product_repository import get_candidate_products_by_brand
from app.repositories.vision_feature_cache_repository import (
    VisionFeatureCacheRepository,
)
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)


class SimilarSKUsService:
    """Service for finding similar SKUs based on vision features."""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        """
        Initialize service.
        
        Args:
            vector_store: Vector store instance (optional, will create if needed)
        """
        self.vector_store = vector_store

    async def search_similar_skus(
        self,
        db: Session,
        brand_code: str,
        vision_features: Optional[Dict] = None,
        trace_id: Optional[str] = None,
        top_k: int = 5,
        mode: str = "rule",
    ) -> Tuple[List[str], bool]:
        """
        搜索相似 SKU。
        
        Args:
            db: Database session
            brand_code: Brand code
            vision_features: Vision features dict (category, style, color, season, keywords)
            top_k: Maximum number of results (<=5)
            mode: Search mode ("rule" or "vector")
        
        Returns:
            Tuple of (sku_list, fallback_used)
            - sku_list: List of SKU strings (最多 top_k 个)
            - fallback_used: Whether fallback to rule mode was used
        """
        logger.info("=" * 80)
        logger.info(
            f"[SIMILAR_SKUS] ========== Similar SKUs Search =========="
        )
        logger.info(
            f"[SIMILAR_SKUS] Input: brand_code={brand_code}, top_k={top_k}, mode={mode}"
        )
        logger.info(
            f"[SIMILAR_SKUS] Input: trace_id={trace_id}, vision_features={'provided' if vision_features else 'none'}"
        )

        fallback_used = False

        try:
            # Step 0: 解析 vision_features（从 trace_id 或直接传入）
            logger.info("[SIMILAR_SKUS] Step 0: Resolving vision features...")
            resolved_features, resolved_brand_code, resolution_failed = await self._resolve_features(
                db, trace_id, vision_features, brand_code
            )
            if resolution_failed:
                logger.error("[SIMILAR_SKUS] ✗ Failed to resolve vision features (trace_id not found or expired)")
                # Raise exception to signal API layer that trace_id resolution failed
                raise ValueError(f"trace_id not found or expired: {trace_id}")
            if not resolved_features:
                logger.error("[SIMILAR_SKUS] ✗ Failed to resolve vision features (empty features)")
                raise ValueError("vision_features is empty")
            logger.info(f"[SIMILAR_SKUS] ✓ Vision features resolved: {resolved_features}")

            # 使用解析后的 brand_code（如果从 trace_id 获取）
            if resolved_brand_code:
                brand_code = resolved_brand_code
            if mode == "vector":
                logger.info("[SIMILAR_SKUS] Step 1: Attempting vector search...")
                try:
                    skus = await self._search_vector(
                        db, brand_code, resolved_features, top_k
                    )
                    if skus:
                        logger.info(f"[SIMILAR_SKUS] ✓ Vector search succeeded: {len(skus)} SKUs")
                        return skus, fallback_used
                    else:
                        logger.warning("[SIMILAR_SKUS] Vector search returned no results, falling back to rule")
                        fallback_used = True
                except Exception as e:
                    logger.warning(f"[SIMILAR_SKUS] Vector search failed: {e}, falling back to rule")
                    fallback_used = True

            # Rule mode (default or fallback)
            logger.info("[SIMILAR_SKUS] Step 2: Using rule-based search...")
            skus = await self._search_rule(db, brand_code, resolved_features, top_k)
            logger.info(f"[SIMILAR_SKUS] ✓ Rule search completed: {len(skus)} SKUs")
            logger.info("=" * 80)

            return skus, fallback_used

        except Exception as e:
            logger.error(f"[SIMILAR_SKUS] ✗ Search failed: {e}", exc_info=True)
            logger.info("=" * 80)
            raise

    async def _resolve_features(
        self,
        db: Session,
        trace_id: Optional[str],
        vision_features: Optional[Dict],
        brand_code: str,
    ) -> Tuple[Optional[Dict], Optional[str], bool]:
        """
        解析 vision_features（从 trace_id 或直接传入）。
        
        Args:
            db: Database session
            trace_id: 追踪ID（可选）
            vision_features: 视觉特征字典（可选）
            brand_code: 品牌编码（用于验证）
        
        Returns:
            Tuple of (vision_features_dict, resolved_brand_code, resolution_failed)
            - vision_features_dict: 解析后的特征字典，如果失败返回 None
            - resolved_brand_code: 从 trace_id 解析出的 brand_code（如果存在），否则返回 None
            - resolution_failed: True 表示 trace_id 未找到或过期（需要返回错误），False 表示成功解析
        """
        # 如果直接提供了 vision_features，直接返回
        if vision_features:
            logger.info("[SIMILAR_SKUS] Using provided vision_features")
            return vision_features, None, False

        # 如果提供了 trace_id，从缓存获取
        if trace_id:
            logger.info(f"[SIMILAR_SKUS] Resolving from trace_id: {trace_id}")
            cached_data = VisionFeatureCacheRepository.get(db, trace_id)
            if cached_data:
                cached_brand_code = cached_data.get("brand_code")
                cached_features = cached_data.get("vision_features", {})
                
                # 验证 brand_code 是否匹配（如果提供）
                if brand_code and cached_brand_code != brand_code:
                    logger.warning(
                        f"[SIMILAR_SKUS] Brand code mismatch: "
                        f"requested={brand_code}, cached={cached_brand_code}"
                    )
                    # 仍然返回缓存的数据，但记录警告
                
                logger.info(f"[SIMILAR_SKUS] ✓ Resolved from cache: {cached_features}")
                return cached_features, cached_brand_code, False
            else:
                logger.error(f"[SIMILAR_SKUS] ✗ Trace ID not found or expired: {trace_id}")
                return None, None, True  # resolution_failed = True

        # 两者都没有提供
        logger.error("[SIMILAR_SKUS] ✗ Neither trace_id nor vision_features provided")
        return None, None, True  # resolution_failed = True

    async def _search_rule(
        self,
        db: Session,
        brand_code: str,
        vision_features: Dict,
        top_k: int,
    ) -> List[str]:
        """
        规则检索模式。
        
        流程：
        1. 从 products 表获取候选商品（brand_code + category 过滤）
        2. 在 Python 中打分排序
        3. 去重并取 top_k
        """
        # Step 1: 获取候选商品（不传 category，在 Python 中过滤）
        candidates = get_candidate_products_by_brand(
            db, brand_code, category=None, limit=300, check_on_sale=True
        )

        if not candidates:
            logger.warning("[SIMILAR_SKUS] No candidates found")
            return []

        initial_count = len(candidates)
        logger.info(f"[SIMILAR_SKUS] Found {initial_count} initial candidates from database")

        # 统计候选商品的 category 分布（用于调试）
        category_distribution = {}
        for product in candidates[:10]:  # 只统计前10个，避免日志过多
            product_category = self._extract_category(product)
            if product_category:
                category_key = str(product_category)
                category_distribution[category_key] = category_distribution.get(category_key, 0) + 1
        logger.info(f"[SIMILAR_SKUS] Category distribution (sample of first 10): {category_distribution}")

        # 在 Python 中过滤 category（如果提供）
        category = vision_features.get("category")
        if category:
            logger.info(f"[SIMILAR_SKUS] Filtering by category: '{category}'")
            filtered_candidates = []
            match_details = []
            for i, product in enumerate(candidates):
                product_category = self._extract_category(product)
                if product_category:
                    product_category_str = str(product_category)
                    # 尝试多种匹配方式
                    if category in product_category_str or product_category_str in category:
                        filtered_candidates.append(product)
                        if len(match_details) < 3:  # 记录前3个匹配的示例
                            match_details.append(f"  Product {i} (SKU: {product.sku}): '{product_category_str}' matches '{category}'")
                    elif i < 5:  # 记录前5个不匹配的示例
                        match_details.append(f"  Product {i} (SKU: {product.sku}): '{product_category_str}' does NOT match '{category}'")
                elif i < 5:
                    match_details.append(f"  Product {i} (SKU: {product.sku}): category is None/empty")
            
            if match_details:
                logger.info(f"[SIMILAR_SKUS] Category filter details:\n" + "\n".join(match_details))
            
            removed_count = initial_count - len(filtered_candidates)
            candidates = filtered_candidates
            logger.info(f"[SIMILAR_SKUS] After category filter: {len(candidates)} candidates (removed {removed_count} candidates)")
        else:
            logger.info("[SIMILAR_SKUS] No category filter applied (category is None or empty)")

        logger.info(f"[SIMILAR_SKUS] Final candidate count: {len(candidates)}")

        # Step 2: 打分
        logger.info(f"[SIMILAR_SKUS] Starting scoring for {len(candidates)} candidates")
        logger.info(f"[SIMILAR_SKUS] Vision features for scoring: category={vision_features.get('category')}, "
                   f"style={vision_features.get('style')}, color={vision_features.get('color')}, "
                   f"colors={vision_features.get('colors')}, season={vision_features.get('season')}, "
                   f"keywords={vision_features.get('keywords')}")
        scored_products = self._score_candidates(candidates, vision_features)

        # Step 3: 去重并排序
        logger.info(f"[SIMILAR_SKUS] Scoring completed: {len(scored_products)} scored products")
        if scored_products:
            top_5_scores = [(sku, score) for sku, score in [(p.sku, s) for p, s in scored_products[:5]]]
            logger.info(f"[SIMILAR_SKUS] Top 5 scores: {top_5_scores}")
        skus = self._dedupe_and_limit(scored_products, top_k)
        logger.info(f"[SIMILAR_SKUS] After deduplication and limit: {len(skus)} SKUs")

        return skus

    def _score_candidates(
        self, candidates: List[Product], vision_features: Dict
    ) -> List[Tuple[Product, float]]:
        """
        对候选商品打分。
        
        评分权重（100分制）：
        - category: 60（精确匹配满分）
        - colors: 10（集合 Jaccard）
        - style: 15（集合匹配，最多15）
        - season: 5
        - material: 5（仅明确时加分，不做推断）
        - keywords: 5（name/tags/attributes 文本浅匹配）
        """
        logger.info(f"[SIMILAR_SKUS] Scoring {len(candidates)} candidates...")

        scored = []
        target_category = vision_features.get("category")
        target_style = set(vision_features.get("style", []))
        target_color = vision_features.get("color")
        target_season = vision_features.get("season")
        target_keywords = set(vision_features.get("keywords", []))

        score_details = []  # 用于记录前5个商品的详细得分
        for idx, product in enumerate(candidates):
            score = 0.0
            score_breakdown = {
                "sku": product.sku,
                "category": 0.0,
                "colors": 0.0,
                "style": 0.0,
                "season": 0.0,
                "keywords": 0.0,
                "total": 0.0,
            }

            # 1. Category score (60 points)
            product_category = self._extract_category(product)
            if target_category and product_category:
                product_category_str = str(product_category)
                if target_category in product_category_str or product_category_str in target_category:
                    score += 60.0
                    score_breakdown["category"] = 60.0
                else:
                    # Partial match: 30 points
                    if any(word in product_category_str for word in target_category.split()) or \
                       any(word in target_category for word in product_category_str.split()):
                        score += 30.0
                        score_breakdown["category"] = 30.0

            # 2. Colors score (10 points, Jaccard similarity)
            # 支持 colors 列表（优先）或 color 单值
            target_colors_list = vision_features.get("colors", [])
            if not target_colors_list and target_color:
                target_colors_list = [target_color]
            
            product_colors = self._extract_colors(product)
            if target_colors_list and product_colors:
                target_colors_set = {c.lower() for c in target_colors_list}
                product_colors_set = {c.lower() for c in product_colors}
                intersection = target_colors_set & product_colors_set
                if intersection:
                    score += 10.0
                    score_breakdown["colors"] = 10.0
                else:
                    # Partial match: 5 points
                    if any(tc in pc or pc in tc for tc in target_colors_set for pc in product_colors_set):
                        score += 5.0
                        score_breakdown["colors"] = 5.0

            # 3. Style score (10 points, set matching)
            product_style = self._extract_style(product)
            if target_style and product_style:
                intersection = target_style & product_style
                if intersection:
                    # 每个匹配的风格给 3.33 分，最多 10 分
                    style_score = min(len(intersection) * 3.33, 10.0)
                    score += style_score
                    score_breakdown["style"] = style_score

            # 4. Season score (10 points)
            product_season = self._extract_season(product)
            if target_season and product_season:
                if target_season in str(product_season) or str(product_season) in target_season:
                    score += 10.0
                    score_breakdown["season"] = 10.0

            # 5. Keywords score (10 points, text matching)
            if target_keywords:
                text_content = f"{product.name} {' '.join(product.tags or [])} {str(product.attributes or {})}"
                text_lower = text_content.lower()
                matched_keywords = sum(1 for kw in target_keywords if kw.lower() in text_lower)
                if matched_keywords > 0:
                    keyword_score = min(matched_keywords * 3.33, 10.0)
                    score += keyword_score
                    score_breakdown["keywords"] = keyword_score

            scored.append((product, score))

        # Sort by score desc, then by updated_at desc
        scored.sort(key=lambda x: (x[1], x[0].updated_at.timestamp() if hasattr(x[0].updated_at, 'timestamp') else 0), reverse=True)

        # 输出详细得分信息
        if score_details:
            logger.info(f"[SIMILAR_SKUS] Detailed score breakdown for first 5 products:")
            for detail in score_details:
                logger.info(f"  SKU {detail['sku']}: category={detail['category']:.1f}, "
                          f"colors={detail['colors']:.1f}, style={detail['style']:.1f}, "
                          f"season={detail['season']:.1f}, keywords={detail['keywords']:.1f}, "
                          f"total={detail['total']:.1f}")
        
        logger.info(f"[SIMILAR_SKUS] ✓ Scoring completed: {len(scored)} products scored, "
                   f"top score: {scored[0][1] if scored else 0:.1f}, "
                   f"min score: {scored[-1][1] if scored else 0:.1f}")
        return scored

    def _extract_category(self, product: Product) -> Optional[str]:
        """提取商品类型（优先级：category列 > attributes["category"] > attributes["类目"]）。"""
        if hasattr(product, "category") and product.category:
            return str(product.category)
        if product.attributes:
            return product.attributes.get("category") or product.attributes.get("类目")
        return None

    def _extract_colors(self, product: Product) -> List[str]:
        """提取颜色（优先级：attributes["colors"] 或 attributes["颜色"]）。"""
        if product.attributes:
            colors = product.attributes.get("colors") or product.attributes.get("颜色")
            if colors:
                if isinstance(colors, list):
                    return colors
                elif isinstance(colors, str):
                    return [c.strip() for c in colors.split(",") if c.strip()]
        return []

    def _extract_style(self, product: Product) -> set:
        """提取风格（从 tags 或 attributes）。"""
        style_set = set()
        if product.tags:
            for tag in product.tags:
                if isinstance(tag, str):
                    style_set.add(tag)
        if product.attributes:
            style = product.attributes.get("style") or product.attributes.get("风格")
            if style:
                if isinstance(style, list):
                    style_set.update(style)
                elif isinstance(style, str):
                    style_set.add(style)
        return style_set

    def _extract_season(self, product: Product) -> Optional[str]:
        """提取季节（从 attributes）。"""
        if product.attributes:
            return product.attributes.get("season") or product.attributes.get("季节")
        return None

    def _extract_material(self, product: Product) -> Optional[str]:
        """提取材质（从 attributes，仅明确标注的）。"""
        if product.attributes:
            return product.attributes.get("material") or product.attributes.get("材质")
        return None

    def _dedupe_and_limit(
        self, scored_products: List[Tuple[Product, float]], top_k: int
    ) -> List[str]:
        """
        去重并限制数量。
        
        去重规则：按 (brand_code, sku) 去重
        排序：按 score desc, updated_at desc
        """
        seen = set()
        result = []

        for product, score in scored_products:
            key = (product.brand_code, product.sku)
            if key not in seen:
                seen.add(key)
                result.append(product.sku)
                if len(result) >= top_k:
                    break

        logger.info(f"[SIMILAR_SKUS] Deduplicated: {len(result)} SKUs")
        return result

    async def _search_vector(
        self,
        db: Session,
        brand_code: str,
        vision_features: Dict,
        top_k: int,
    ) -> List[str]:
        """
        向量检索模式。
        
        流程：
        1. 构建查询文本（category + style + color + season + keywords）
        2. 调用 vector_store.search
        3. metadata filter 包含 brand_code
        4. 从 document_id 提取 sku（格式：brand_code#sku）
        5. 去重并限制数量
        """
        # Build query text
        query_parts = []
        if vision_features.get("category"):
            query_parts.append(vision_features["category"])
        if vision_features.get("style"):
            query_parts.extend(vision_features["style"])
        if vision_features.get("color"):
            query_parts.append(vision_features["color"])
        if vision_features.get("season"):
            query_parts.append(vision_features["season"])
        if vision_features.get("keywords"):
            query_parts.extend(vision_features["keywords"])

        query_text = " ".join(query_parts)
        if not query_text.strip():
            logger.warning("[SIMILAR_SKUS] Empty query text for vector search")
            return []

        logger.info(f"[SIMILAR_SKUS] Vector query: {query_text}")

        # Get vector store
        if self.vector_store is None:
            self.vector_store = VectorStore()
            if not self.vector_store.load():
                raise RuntimeError("Vector store not available")

        # Search (top_k * 2 to account for filtering)
        try:
            # VectorStore.search returns List[Tuple[str, float]] (chunk_text, distance)
            # For incremental mode, we need to get document_id from chunk metadata
            results = self.vector_store.search(query_text, top_k=top_k * 2)
        except Exception as e:
            logger.error(f"[SIMILAR_SKUS] Vector search error: {e}")
            raise

        # Extract SKUs from results
        # Note: VectorStore.search returns (chunk_text, distance)
        # We need to match chunks to document_ids if using incremental mode
        skus = []
        seen = set()

        # Try to get document_ids from vector store (if incremental mode)
        # Note: VectorStore.search returns (chunk_text, distance), but we need document_id
        # We need to match chunks to document_ids by finding the chunk index
        
        if not self.vector_store.use_incremental:
            logger.warning("[SIMILAR_SKUS] Vector search requires incremental mode for document_id extraction")
            return []
        
        # Build mapping from chunk text to document_id
        # We need to search through delta and base chunks to find matching document_ids
        chunk_to_doc_id = {}
        
        # Build mapping from chunks to document_ids (delta takes priority)
        if self.vector_store.delta_chunks and self.vector_store.delta_document_ids:
            for chunk, doc_id in zip(self.vector_store.delta_chunks, self.vector_store.delta_document_ids):
                chunk_to_doc_id[chunk] = doc_id
        
        if self.vector_store.base_chunks and self.vector_store.base_document_ids:
            for chunk, doc_id in zip(self.vector_store.base_chunks, self.vector_store.base_document_ids):
                if chunk not in chunk_to_doc_id:  # Delta takes priority
                    chunk_to_doc_id[chunk] = doc_id
        
        # Extract SKUs from results
        for chunk_text, distance in results:
            document_id = chunk_to_doc_id.get(chunk_text)
            if not document_id:
                # Try partial match (in case chunk text is truncated)
                for stored_chunk, doc_id in chunk_to_doc_id.items():
                    if chunk_text in stored_chunk or stored_chunk in chunk_text:
                        document_id = doc_id
                        break
            
            if not document_id:
                continue
            
            # Parse document_id: brand_code#sku
            if "#" in document_id:
                doc_brand_code, sku = document_id.split("#", 1)
                if doc_brand_code == brand_code:
                    key = (brand_code, sku)
                    if key not in seen:
                        seen.add(key)
                        skus.append(sku)
                        if len(skus) >= top_k:
                            break

        logger.info(f"[SIMILAR_SKUS] Vector search returned {len(skus)} SKUs")
        return skus


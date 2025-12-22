"""Product vector text builder for stable text generation."""
from __future__ import annotations

import logging
from typing import Any

from app.models.product import Product
from app.utils.json_utils import stable_json_dumps

logger = logging.getLogger(__name__)


class ProductVectorTextBuilder:
    """Builder for constructing stable vector text from Product objects."""

    @classmethod
    def build_vector_text(cls, product: Product) -> str:
        """
        Build stable vector text from Product object.
        
        Construction rules:
        - name (required)
        - tags: stable JSON serialization (sorted, deduplicated)
        - attributes: stable JSON serialization (sorted keys, values normalized)
        - price (optional): converted to string
        - on_sale (optional): boolean converted to string
        
        The text must be stable: same product data should produce same text
        every day to avoid vector jitter.
        
        Args:
            product: Product object
            
        Returns:
            Stable text string for vector embedding
        """
        parts = []
        
        # 1. Name (required)
        if product.name:
            parts.append(product.name)
        else:
            parts.append("")  # Empty name placeholder
        
        # 2. Tags: stable JSON serialization
        if product.tags:
            if isinstance(product.tags, (list, dict)):
                tags_text = stable_json_dumps(product.tags)
                parts.append(f"标签: {tags_text}")
            else:
                # If tags is a string, use as-is
                parts.append(f"标签: {product.tags}")
        
        # 3. Attributes: stable JSON serialization
        if product.attributes:
            if isinstance(product.attributes, dict):
                attrs_text = stable_json_dumps(product.attributes)
                parts.append(f"属性: {attrs_text}")
            else:
                # If attributes is a string, use as-is
                parts.append(f"属性: {product.attributes}")
        
        # 4. Price (optional): convert to string
        if product.price is not None:
            # Convert Decimal/float to string for stability
            price_str = str(product.price)
            parts.append(f"价格: {price_str}")
        
        # 5. on_sale (optional): check if column exists
        # Note: on_sale may not exist in all Product models
        if hasattr(product, "on_sale") and product.on_sale is not None:
            on_sale_str = "在售" if product.on_sale else "下架"
            parts.append(f"状态: {on_sale_str}")
        
        # Join all parts with newlines for readability
        text = "\n".join(parts)
        
        logger.debug(
            f"[VECTOR_TEXT_BUILDER] Built text for product "
            f"(brand_code={product.brand_code}, sku={product.sku}, "
            f"text_length={len(text)})"
        )
        
        return text


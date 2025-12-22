"""Product normalizer for JSON field processing."""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ProductNormalizer:
    """Normalize product data from staging format to products format."""

    @staticmethod
    def normalize_colors(colors_concat: str | None) -> list[str]:
        """
        Normalize colors from colors_concat string.
        
        Rules:
        - Split by '||' separator
        - Deduplicate and sort
        - Return empty list if None or empty
        
        Args:
            colors_concat: '||' separated string (e.g., "红色||蓝色||红色")
            
        Returns:
            Sorted list of unique colors (e.g., ["蓝色", "红色"])
        """
        if not colors_concat or not colors_concat.strip():
            return []
        
        # Split by '||'
        colors = [c.strip() for c in colors_concat.split("||") if c.strip()]
        
        # Deduplicate and sort
        unique_colors = sorted(list(set(colors)))
        
        logger.debug(f"[NORMALIZER] Normalized colors: {colors_concat} -> {unique_colors}")
        return unique_colors

    @staticmethod
    def normalize_tags(tags_json: Any) -> list[str]:
        """
        Normalize tags from tags_json.
        
        Rules:
        - If tags_json is already a list, use it directly
        - If tags_json is a JSON string, parse it
        - If tags_json is None or empty, return []
        - Deduplicate and sort
        
        Args:
            tags_json: JSON array or None
            
        Returns:
            Sorted list of unique tags
        """
        if tags_json is None:
            return []
        
        # If already a list, use it
        if isinstance(tags_json, list):
            tags = tags_json
        elif isinstance(tags_json, str):
            # Try to parse JSON string
            try:
                tags = json.loads(tags_json)
                if not isinstance(tags, list):
                    logger.warning(f"[NORMALIZER] tags_json is not a list: {tags_json}")
                    return []
            except json.JSONDecodeError:
                logger.warning(f"[NORMALIZER] Failed to parse tags_json: {tags_json}")
                return []
        else:
            logger.warning(f"[NORMALIZER] Unexpected tags_json type: {type(tags_json)}")
            return []
        
        # Filter out empty strings and None
        tags = [str(tag).strip() for tag in tags if tag and str(tag).strip()]
        
        # Deduplicate and sort
        unique_tags = sorted(list(set(tags)))
        
        logger.debug(f"[NORMALIZER] Normalized tags: {tags_json} -> {unique_tags}")
        return unique_tags

    @staticmethod
    def normalize_attributes(attrs_json: Any) -> dict[str, Any]:
        """
        Normalize attributes from attrs_json.
        
        Rules:
        - If attrs_json is already a dict, use it directly
        - If attrs_json is a JSON string, parse it
        - If attrs_json is None or empty, return {}
        - For values containing '||', split into array
        - Single values remain as string
        - Remove empty/null values
        
        Args:
            attrs_json: JSON object or None
            
        Returns:
            Normalized attributes dictionary
        """
        if attrs_json is None:
            return {}
        
        # If already a dict, use it
        if isinstance(attrs_json, dict):
            attrs = attrs_json
        elif isinstance(attrs_json, str):
            # Try to parse JSON string
            try:
                attrs = json.loads(attrs_json)
                if not isinstance(attrs, dict):
                    logger.warning(f"[NORMALIZER] attrs_json is not a dict: {attrs_json}")
                    return {}
            except json.JSONDecodeError:
                logger.warning(f"[NORMALIZER] Failed to parse attrs_json: {attrs_json}")
                return {}
        else:
            logger.warning(f"[NORMALIZER] Unexpected attrs_json type: {type(attrs_json)}")
            return {}
        
        # Normalize values: split by '||' if contains '||', otherwise keep as string
        normalized_attrs = {}
        for key, value in attrs.items():
            if value is None:
                continue  # Skip None values
            
            value_str = str(value).strip()
            if not value_str or value_str in ("无", "不适用", "空", "--", ""):
                continue  # Skip invalid values
            
            # If contains '||', split into array
            if "||" in value_str:
                parts = [p.strip() for p in value_str.split("||") if p.strip()]
                if parts:
                    normalized_attrs[key] = sorted(list(set(parts)))  # Deduplicate and sort
            else:
                normalized_attrs[key] = value_str
        
        logger.debug(f"[NORMALIZER] Normalized attributes: {attrs_json} -> {normalized_attrs}")
        return normalized_attrs

    @classmethod
    def normalize_staging_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize a complete staging record to products format.
        
        Args:
            record: Staging record dictionary with keys:
                - style_brand_no: str -> brand_code (required)
                - style_no: str -> sku (required)
                - name: str (optional, may be None)
                - price: Decimal or str (optional, may be None)
                - colors_concat: str | None -> colors (list)
                - tags_json: Any -> tags (list)
                - attrs_json: Any -> attributes (dict)
                - description: str | None
                - image_url: str | None
                - on_sale: bool | None
                
        Returns:
            Normalized product data dictionary
        """
        # Required fields
        brand_code = record.get("style_brand_no")
        sku = record.get("style_no")
        
        if not brand_code or not sku:
            raise ValueError(
                f"Missing required fields: style_brand_no={brand_code}, style_no={sku}"
            )
        
        normalized = {
            "brand_code": brand_code,
            "sku": sku,
            "name": record.get("name") or "",  # Default to empty string if None
            "price": record.get("price") or "0.00",  # Default to "0.00" if None
            "colors": cls.normalize_colors(record.get("colors_concat")),
            "tags": cls.normalize_tags(record.get("tags_json")),
            "attributes": cls.normalize_attributes(record.get("attrs_json")),
            "description": record.get("description"),
            "image_url": record.get("image_url"),
        }
        
        # Add on_sale if exists
        if "on_sale" in record:
            normalized["on_sale"] = record["on_sale"]
        
        logger.debug(
            f"[NORMALIZER] Normalized record: "
            f"brand_code={normalized['brand_code']}, sku={normalized['sku']}"
        )
        return normalized


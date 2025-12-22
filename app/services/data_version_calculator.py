"""Data version calculator for product change detection."""
from __future__ import annotations

import hashlib
import logging
from decimal import Decimal
from typing import Any

from app.utils.json_utils import stable_json_dumps

logger = logging.getLogger(__name__)


class DataVersionCalculator:
    """Calculate stable data version hash for change detection."""

    # Field whitelist for data_version calculation
    WHITELIST_FIELDS = [
        "brand_code",
        "sku",
        "name",
        "price",
        "image_url",
        "on_sale",
        "tags",
        "attributes",
    ]

    @classmethod
    def calculate_data_version(cls, product_data: dict[str, Any]) -> str:
        """
        Calculate stable data version hash.
        
        Rules:
        - Only include whitelist fields
        - Use stable JSON serialization (key sorted, list deduplicated and sorted)
        - Price must be Decimal or str, NOT float
        - Return MD5 hash of normalized JSON string
        
        Args:
            product_data: Product data dictionary
            
        Returns:
            MD5 hash string (32 characters)
        """
        # Extract whitelist fields only
        normalized_data = {}
        for field in cls.WHITELIST_FIELDS:
            if field in product_data:
                value = product_data[field]
                
                # Special handling for price: ensure it's Decimal or str, not float
                if field == "price":
                    if isinstance(value, float):
                        logger.warning(
                            f"[DATA_VERSION] Price is float, converting to string: {value}"
                        )
                        value = str(value)
                    elif isinstance(value, Decimal):
                        value = str(value)
                    elif not isinstance(value, str):
                        value = str(value)
                
                normalized_data[field] = value
        
        # Stable JSON serialization
        json_str = stable_json_dumps(normalized_data, sort_keys=True)
        
        # Calculate MD5 hash
        hash_obj = hashlib.md5(json_str.encode("utf-8"))
        data_version = hash_obj.hexdigest()
        
        logger.debug(
            f"[DATA_VERSION] Calculated version: "
            f"brand_code={product_data.get('brand_code')}, "
            f"sku={product_data.get('sku')}, "
            f"version={data_version}"
        )
        
        return data_version


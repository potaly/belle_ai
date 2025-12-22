"""Product staging repository for ETL batch processing."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ProductStagingRepository:
    """Repository for querying products_staging table in batches."""

    def __init__(self, db: Session):
        """
        Initialize repository.
        
        Args:
            db: Database session
        """
        self.db = db

    def _get_table_columns(self, table_name: str) -> set[str]:
        """
        Get actual column names from table.
        
        Args:
            table_name: Table name
            
        Returns:
            Set of column names
        """
        sql = f"SHOW COLUMNS FROM {table_name}"
        result = self.db.execute(text(sql))
        return {row.Field for row in result}

    def fetch_batch_by_watermark(
        self,
        table_name: str,
        last_processed_at: Optional[datetime],
        last_processed_key: Optional[str],
        limit: int = 1000,
    ) -> list[dict]:
        """
        Fetch batch of records from products_staging using watermark.
        
        Supports "same-second no-miss" design:
        - watermark: last_processed_at + last_processed_key (key = style_brand_no#style_no)
        - Fetch condition: src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)
        - Order by: src_updated_at, style_brand_no, style_no
        
        Args:
            table_name: Table name (e.g., 'products_staging')
            last_processed_at: Last processed timestamp (None for first run)
            last_processed_key: Last processed key (None for first run)
            limit: Batch size limit
            
        Returns:
            List of record dictionaries
        """
        logger.info(
            f"[STAGING_REPO] Fetching batch: table={table_name}, "
            f"last_at={last_processed_at}, last_key={last_processed_key}, limit={limit}"
        )
        
        # Get actual table columns
        actual_columns = self._get_table_columns(table_name)
        logger.info(f"[STAGING_REPO] Actual columns in {table_name}: {sorted(actual_columns)}")
        
        # Build WHERE condition
        if last_processed_at is None or last_processed_key is None:
            # First run: fetch all records
            where_clause = "1=1"
            params: dict[str, Any] = {}
        else:
            # Incremental: src_updated_at > last_at OR (src_updated_at = last_at AND key > last_key)
            where_clause = (
                "src_updated_at > :last_at OR "
                "(src_updated_at = :last_at AND CONCAT(style_brand_no, '#', style_no) > :last_key)"
            )
            params = {
                "last_at": last_processed_at,
                "last_key": last_processed_key,
            }
        
        # Build SELECT fields dynamically based on actual columns
        # Required fields: style_brand_no, style_no, src_updated_at
        required_fields = {"style_brand_no", "style_no", "src_updated_at"}
        if not required_fields.issubset(actual_columns):
            missing = required_fields - actual_columns
            raise ValueError(
                f"Missing required fields in {table_name}: {missing}. "
                f"Available columns: {actual_columns}"
            )
        
        # Optional fields with fallback (order matters - first match wins)
        field_mapping = {
            "name": ["commodity_name", "name", "product_name", "style_name", "prod_name", "item_name"],  # commodity_name is the actual field in products_staging
            "price": ["price", "sale_price", "retail_price"],
            "colors_concat": ["colors_concat", "colors", "color_concat"],
            "tags_json": ["tags_json", "tags", "tag_json"],
            "attrs_json": ["attrs_json", "attributes", "attrs", "attribute_json"],
            "description": ["description", "desc", "product_desc"],
            "image_url": ["image_url", "image", "img_url", "pic_url", "main_image"],
            "on_sale": ["on_sale", "onsale", "is_on_sale", "is_sale"],
        }
        
        select_fields = ["style_brand_no", "style_no", "src_updated_at"]
        field_aliases = {
            "style_brand_no": "style_brand_no",
            "style_no": "style_no",
            "src_updated_at": "src_updated_at",
        }
        
        # Add optional fields if they exist
        for target_field, possible_names in field_mapping.items():
            found = False
            for possible_name in possible_names:
                if possible_name in actual_columns:
                    select_fields.append(possible_name)
                    field_aliases[target_field] = possible_name
                    logger.debug(f"[STAGING_REPO] Mapped {target_field} -> {possible_name}")
                    found = True
                    break
            if not found:
                logger.warning(f"[STAGING_REPO] Field {target_field} not found in table, will use None")
                field_aliases[target_field] = None  # Mark as not found
        
        # Build SQL query
        select_clause = ", ".join(select_fields)
        sql = f"""
        SELECT {select_clause}
        FROM {table_name}
        WHERE {where_clause}
        ORDER BY src_updated_at ASC, style_brand_no ASC, style_no ASC
        LIMIT :limit
        """
        
        params["limit"] = limit
        
        # Execute query
        result = self.db.execute(text(sql), params)
        records = []
        for row in result:
            record = {
                "style_brand_no": getattr(row, "style_brand_no", None),
                "style_no": getattr(row, "style_no", None),
                "src_updated_at": getattr(row, "src_updated_at", None),
            }
            
            # Add optional fields with fallback
            for target_field, actual_field in field_aliases.items():
                if target_field not in ("style_brand_no", "style_no", "src_updated_at"):
                    if actual_field is None:
                        # Field not found in table
                        record[target_field] = None
                    else:
                        # Use row attribute access (works with both column names and aliases)
                        # Try direct attribute access first
                        value = getattr(row, actual_field, None)
                        # If that fails, try dictionary access (for case-sensitive issues)
                        if value is None and hasattr(row, '_mapping'):
                            value = row._mapping.get(actual_field)
                        record[target_field] = value
            
            records.append(record)
        
        # Log first record structure for debugging
        if records:
            logger.debug(f"[STAGING_REPO] Sample record keys: {list(records[0].keys())}")
            logger.debug(f"[STAGING_REPO] Sample record (first 3 fields): {dict(list(records[0].items())[:3])}")
        
        logger.info(f"[STAGING_REPO] ✓ Fetched {len(records)} records")
        return records

    def get_max_updated_at_and_key(
        self, records: list[dict]
    ) -> tuple[Optional[datetime], Optional[str]]:
        """
        Get maximum src_updated_at and corresponding key from records.
        
        Args:
            records: List of record dictionaries
            
        Returns:
            Tuple of (max_updated_at, max_key) where key = style_brand_no#style_no
        """
        if not records:
            return None, None
        
        # Find max src_updated_at
        max_updated_at = max(r["src_updated_at"] for r in records)
        
        # Find max key among records with max src_updated_at
        max_records = [r for r in records if r["src_updated_at"] == max_updated_at]
        max_key = max(
            f"{r['style_brand_no']}#{r['style_no']}" for r in max_records
        )
        
        return max_updated_at, max_key


"""ETL product worker for batch processing products_staging."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.etl_watermark import ETLWatermark
from app.repositories.product_staging_repository import ProductStagingRepository
from app.services.product_normalizer import ProductNormalizer
from app.services.product_upsert_service import ProductUpsertService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


class ETLProductWorker:
    """ETL worker for processing products_staging to products."""

    TABLE_NAME = "products_staging"

    def __init__(self, db: Session, limit: int = 1000):
        """
        Initialize ETL worker.
        
        Args:
            db: Database session
            limit: Batch size limit
        """
        self.db = db
        self.limit = limit
        self.staging_repo = ProductStagingRepository(db)
        self.upsert_service = ProductUpsertService(db)

    def validate_prerequisites(self) -> None:
        """
        Validate prerequisites before running ETL.
        
        Checks:
        1. products table has UNIQUE(brand_code, sku) constraint
        2. products_staging table has required fields:
           - style_brand_no, style_no, src_updated_at
        
        Raises:
            SystemExit: If prerequisites are not met
        """
        logger.info("[ETL_WORKER] Validating prerequisites...")
        
        # Check 1: products table UNIQUE(brand_code, sku) constraint
        logger.info("[ETL_WORKER] Checking products table unique constraint...")
        result = self.db.execute(
            text("""
            SHOW INDEX FROM belle_ai.products 
            WHERE Key_name != 'PRIMARY' AND Non_unique = 0
            """)
        )
        
        unique_indexes = []
        for row in result:
            unique_indexes.append({
                "Key_name": row.Key_name,
                "Column_name": row.Column_name,
                "Seq_in_index": row.Seq_in_index,
            })
        
        # Check if idx_products_brand_sku exists with both brand_code and sku
        brand_sku_index = None
        for idx in unique_indexes:
            if idx["Key_name"] == "idx_products_brand_sku":
                brand_sku_index = idx
                break
        
        if not brand_sku_index:
            logger.error(
                "[ETL_WORKER] ❌ UNIQUE(brand_code, sku) constraint not found in products table!"
            )
            logger.error(
                "[ETL_WORKER] Please execute the following SQL to create the constraint:"
            )
            logger.error(
                """
                -- Step 1: Check current indexes
                SHOW INDEX FROM belle_ai.products WHERE Key_name != 'PRIMARY';
                
                -- Step 2: Drop old unique index on sku (if exists)
                -- ALTER TABLE belle_ai.products DROP INDEX <真实索引名>;
                
                -- Step 3: Add new unique constraint
                ALTER TABLE belle_ai.products 
                ADD UNIQUE INDEX idx_products_brand_sku (brand_code, sku);
                
                -- Step 4: Add sku index for query performance
                ALTER TABLE belle_ai.products 
                ADD INDEX idx_products_sku (sku);
                """
            )
            sys.exit(1)
        
        # Verify the index includes both brand_code and sku
        result = self.db.execute(
            text("""
            SELECT Column_name, Seq_in_index 
            FROM information_schema.STATISTICS 
            WHERE table_schema = 'belle_ai' 
              AND table_name = 'products' 
              AND index_name = 'idx_products_brand_sku'
            ORDER BY seq_in_index
            """)
        )
        
        index_columns = [row.Column_name for row in result]
        if "brand_code" not in index_columns or "sku" not in index_columns:
            logger.error(
                "[ETL_WORKER] ❌ idx_products_brand_sku does not include both brand_code and sku!"
            )
            logger.error(f"[ETL_WORKER] Found columns: {index_columns}")
            sys.exit(1)
        
        logger.info("[ETL_WORKER] ✓ products table unique constraint validated")
        
        # Check 2: products_staging table required fields
        logger.info("[ETL_WORKER] Checking products_staging table fields...")
        result = self.db.execute(
            text(f"SHOW COLUMNS FROM belle_ai.{self.TABLE_NAME}")
        )
        
        existing_fields = {row.Field for row in result}
        required_fields = {"style_brand_no", "style_no", "src_updated_at"}
        missing_fields = required_fields - existing_fields
        
        if missing_fields:
            logger.error(
                f"[ETL_WORKER] ❌ products_staging table missing required fields: {missing_fields}"
            )
            logger.error(
                "[ETL_WORKER] Please ensure products_staging table has the following fields:"
            )
            logger.error("  - style_brand_no (VARCHAR)")
            logger.error("  - style_no (VARCHAR)")
            logger.error("  - src_updated_at (DATETIME)")
            sys.exit(1)
        
        logger.info("[ETL_WORKER] ✓ products_staging table fields validated")
        logger.info("[ETL_WORKER] ✓ All prerequisites validated")

    def get_watermark(self) -> tuple[Optional[datetime], Optional[str]]:
        """
        Get watermark from etl_watermark table.
        
        Returns:
            Tuple of (last_processed_at, last_processed_key)
        """
        watermark = (
            self.db.query(ETLWatermark)
            .filter(ETLWatermark.table_name == self.TABLE_NAME)
            .first()
        )
        
        if watermark:
            return watermark.last_processed_at, watermark.last_processed_key
        
        return None, None

    def update_watermark(
        self, last_processed_at: datetime, last_processed_key: str
    ) -> None:
        """
        Update watermark in etl_watermark table.
        
        Args:
            last_processed_at: Last processed timestamp
            last_processed_key: Last processed key (style_brand_no#style_no)
        """
        watermark = (
            self.db.query(ETLWatermark)
            .filter(ETLWatermark.table_name == self.TABLE_NAME)
            .first()
        )
        
        if watermark:
            watermark.last_processed_at = last_processed_at
            watermark.last_processed_key = last_processed_key
        else:
            watermark = ETLWatermark(
                table_name=self.TABLE_NAME,
                last_processed_at=last_processed_at,
                last_processed_key=last_processed_key,
            )
            self.db.add(watermark)
        
        self.db.commit()
        logger.info(
            f"[ETL_WORKER] Watermark updated: "
            f"last_at={last_processed_at}, last_key={last_processed_key}"
        )

    def process_batch(self, resume: bool = True, batch_limit: int | None = None) -> dict[str, int]:
        """
        Process one batch of records.
        
        Args:
            resume: Whether to resume from watermark
            batch_limit: Limit for this batch (None = use self.limit)
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "processed": 0,
            "changed": 0,
            "unchanged": 0,
        }
        
        # Get watermark
        if resume:
            last_at, last_key = self.get_watermark()
        else:
            last_at, last_key = None, None
        
        # Use batch_limit if provided, otherwise use self.limit
        limit = batch_limit if batch_limit is not None else self.limit
        
        # Fetch batch
        records = self.staging_repo.fetch_batch_by_watermark(
            self.TABLE_NAME, last_at, last_key, limit
        )
        
        if not records:
            logger.info("[ETL_WORKER] No more records to process")
            return stats
        
        logger.info(f"[ETL_WORKER] Processing batch of {len(records)} records...")
        
        # Process each record
        for record in records:
            try:
                # Normalize
                normalized = ProductNormalizer.normalize_staging_record(record)
                
                # Upsert
                changed, data_version = self.upsert_service.upsert_product(normalized)
                
                stats["processed"] += 1
                if changed:
                    stats["changed"] += 1
                else:
                    stats["unchanged"] += 1
                    
            except Exception as e:
                logger.error(
                    f"[ETL_WORKER] Error processing record: "
                    f"style_brand_no={record.get('style_brand_no')}, "
                    f"style_no={record.get('style_no')}, error={e}",
                    exc_info=True,
                )
                continue
        
        # Update watermark
        max_at, max_key = self.staging_repo.get_max_updated_at_and_key(records)
        if max_at and max_key:
            self.update_watermark(max_at, max_key)
        
        logger.info(
            f"[ETL_WORKER] Batch processed: "
            f"processed={stats['processed']}, "
            f"changed={stats['changed']}, "
            f"unchanged={stats['unchanged']}"
        )
        
        return stats

    def run(self, resume: bool = True, total_limit: int | None = None) -> None:
        """
        Run ETL worker (process batches up to total_limit records).
        
        Args:
            resume: Whether to resume from watermark
            total_limit: Total number of records to process (None = process all)
        """
        logger.info("=" * 60)
        logger.info("ETL Product Worker Started")
        if total_limit:
            logger.info(f"Total limit: {total_limit} records")
        logger.info("=" * 60)
        
        # Validate prerequisites
        self.validate_prerequisites()
        
        # Process batches
        total_stats = {
            "processed": 0,
            "changed": 0,
            "unchanged": 0,
        }
        
        batch_num = 0
        remaining_limit = total_limit
        
        while True:
            batch_num += 1
            logger.info(f"\n[ETL_WORKER] Processing batch #{batch_num}...")
            
            # Adjust batch limit if total_limit is set
            if total_limit is not None:
                if remaining_limit is not None and remaining_limit <= 0:
                    logger.info(f"[ETL_WORKER] Reached total limit of {total_limit} records")
                    break
                # Use remaining_limit if it's smaller than self.limit
                batch_limit = min(self.limit, remaining_limit) if remaining_limit else self.limit
            else:
                batch_limit = self.limit
            
            batch_stats = self.process_batch(resume=resume, batch_limit=batch_limit)
            
            # Accumulate stats
            for key in total_stats:
                total_stats[key] += batch_stats[key]
            
            # Update remaining limit
            if total_limit is not None and remaining_limit is not None:
                remaining_limit -= batch_stats["processed"]
                if remaining_limit <= 0:
                    logger.info(f"[ETL_WORKER] Reached total limit of {total_limit} records")
                    break
            
            # Stop if no more records
            if batch_stats["processed"] == 0:
                break
        
        # Final summary
        logger.info("\n" + "=" * 60)
        logger.info("ETL Product Worker Completed")
        logger.info("=" * 60)
        logger.info(f"Total processed: {total_stats['processed']}")
        logger.info(f"Total changed: {total_stats['changed']}")
        logger.info(f"Total unchanged: {total_stats['unchanged']}")
        logger.info("=" * 60)


def main():
    """Main entry point for ETL worker."""
    parser = argparse.ArgumentParser(description="ETL Product Worker")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Total number of records to process (default: None, process all)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="Resume from watermark (default: True)",
    )
    parser.add_argument(
        "--no-resume",
        dest="resume",
        action="store_false",
        help="Start from beginning (ignore watermark)",
    )
    
    args = parser.parse_args()
    
    db = SessionLocal()
    try:
        # Use batch size of 1000 for internal batching, but limit total records
        worker = ETLProductWorker(db, limit=1000)  # Internal batch size
        worker.run(resume=args.resume, total_limit=args.limit)
    finally:
        db.close()


if __name__ == "__main__":
    main()


"""Vector sync worker for processing product change logs."""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.etl_watermark import ETLWatermark
from app.repositories.product_change_log_repository import ProductChangeLogRepository
from app.services.vector_sync_service import VectorSyncService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Job name for watermark
JOB_NAME = "vector_sync_worker"
# Default batch size
DEFAULT_BATCH_SIZE = 100


class VectorSyncWorker:
    """Worker for syncing product change logs to vector store."""

    def __init__(self, db: Session, limit: Optional[int] = None):
        """
        Initialize vector sync worker.
        
        Args:
            db: Database session
            limit: Total limit for processing (None = no limit)
        """
        self.db = db
        self.limit = limit
        self.change_log_repo = ProductChangeLogRepository(db)
        self.sync_service = VectorSyncService(db)

    def get_watermark(self) -> Optional[int]:
        """
        Get watermark (last_id) from etl_watermark table.
        
        Returns:
            Last processed ID, or None if not found
        """
        watermark = (
            self.db.query(ETLWatermark)
            .filter(ETLWatermark.table_name == JOB_NAME)
            .first()
        )
        
        if watermark:
            # Parse last_processed_key as last_id (stored as string)
            try:
                last_id = int(watermark.last_processed_key)
                logger.info(f"[VECTOR_SYNC_WORKER] Watermark found: last_id={last_id}")
                return last_id
            except (ValueError, TypeError):
                logger.warning(
                    f"[VECTOR_SYNC_WORKER] Invalid watermark last_processed_key: "
                    f"{watermark.last_processed_key}, starting from beginning"
                )
                return None
        
        logger.info("[VECTOR_SYNC_WORKER] No watermark found, starting from beginning")
        return None

    def update_watermark(self, last_id: int) -> None:
        """
        Update watermark in etl_watermark table.
        
        Args:
            last_id: Last processed change_log ID
        """
        watermark = (
            self.db.query(ETLWatermark)
            .filter(ETLWatermark.table_name == JOB_NAME)
            .first()
        )
        
        if watermark:
            watermark.last_processed_at = datetime.now()
            watermark.last_processed_key = str(last_id)
        else:
            watermark = ETLWatermark(
                table_name=JOB_NAME,
                last_processed_at=datetime.now(),
                last_processed_key=str(last_id),
            )
            self.db.add(watermark)
        
        self.db.commit()
        logger.info(f"[VECTOR_SYNC_WORKER] Watermark updated: last_id={last_id}")

    def process_batch(
        self, resume: bool = True, batch_size: int = DEFAULT_BATCH_SIZE
    ) -> dict[str, int]:
        """
        Process one batch of change log records.
        
        Args:
            resume: Whether to resume from watermark
            batch_size: Batch size for processing
            
        Returns:
            Statistics dictionary
        """
        stats = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        # Get watermark
        if resume:
            last_id = self.get_watermark()
        else:
            last_id = None
        
        # Fetch batch using cursor pagination
        change_logs = self.change_log_repo.fetch_pending_changes(
            limit=batch_size, last_id=last_id
        )
        
        if not change_logs:
            logger.info("[VECTOR_SYNC_WORKER] No more pending change logs to process")
            return stats
        
        logger.info(
            f"[VECTOR_SYNC_WORKER] Processing batch of {len(change_logs)} change logs "
            f"(last_id={last_id})"
        )
        
        # Batch sync
        batch_stats = self.sync_service.sync_change_logs_batch(change_logs)
        
        stats["processed"] = len(change_logs)
        stats["success"] = batch_stats.get("success", 0)
        stats["failed"] = batch_stats.get("failed", 0)
        stats["skipped"] = batch_stats.get("skipped", 0)
        
        # Update watermark with max ID from this batch
        if change_logs:
            max_id = max(log.id for log in change_logs)
            self.update_watermark(max_id)
        
        logger.info(
            f"[VECTOR_SYNC_WORKER] Batch completed: processed={stats['processed']}, "
            f"success={stats['success']}, failed={stats['failed']}, skipped={stats['skipped']}"
        )
        
        return stats

    def run(self, resume: bool = True, total_limit: Optional[int] = None) -> None:
        """
        Run worker to process all pending change logs.
        
        Args:
            resume: Whether to resume from watermark
            total_limit: Total number of records to process (None = no limit)
        """
        logger.info(
            f"[VECTOR_SYNC_WORKER] Starting worker: resume={resume}, "
            f"total_limit={total_limit or 'unlimited'}"
        )
        
        total_stats = {
            "processed": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        batch_num = 0
        
        while True:
            batch_num += 1
            logger.info(f"[VECTOR_SYNC_WORKER] Processing batch #{batch_num}...")
            
            # Process batch
            batch_stats = self.process_batch(resume=resume, batch_size=DEFAULT_BATCH_SIZE)
            
            # Accumulate stats
            for key in total_stats:
                total_stats[key] += batch_stats.get(key, 0)
            
            # Check if we've reached the limit
            if total_limit and total_stats["processed"] >= total_limit:
                logger.info(
                    f"[VECTOR_SYNC_WORKER] Reached total limit: {total_stats['processed']} >= {total_limit}"
                )
                break
            
            # Check if no more records
            if batch_stats["processed"] == 0:
                logger.info("[VECTOR_SYNC_WORKER] No more records to process")
                break
        
        logger.info(
            f"[VECTOR_SYNC_WORKER] Worker completed: "
            f"total_processed={total_stats['processed']}, "
            f"total_success={total_stats['success']}, "
            f"total_failed={total_stats['failed']}, "
            f"total_skipped={total_stats['skipped']}"
        )


def main():
    """Main entry point for vector sync worker."""
    parser = argparse.ArgumentParser(description="Vector sync worker for product change logs")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Total number of records to process (default: unlimited)",
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
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Create worker
        worker = VectorSyncWorker(db, limit=args.limit)
        
        # Run worker
        worker.run(resume=args.resume, total_limit=args.limit)
        
    except KeyboardInterrupt:
        logger.info("[VECTOR_SYNC_WORKER] Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"[VECTOR_SYNC_WORKER] Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()


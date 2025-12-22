"""Vector sync service for processing product change logs."""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.product_change_log import ChangeStatus, ChangeType, ProductChangeLog
from app.repositories.product_repository import get_product_by_brand_and_sku
from app.services.product_vector_text_builder import ProductVectorTextBuilder
from app.services.vector_store import VectorStore

logger = logging.getLogger(__name__)

# Maximum retry count before stopping automatic retries
MAX_VECTOR_RETRY = 3


class VectorSyncService:
    """Service for syncing product changes to vector store."""

    def __init__(self, db: Session, vector_store: Optional[VectorStore] = None):
        """
        Initialize vector sync service.
        
        Args:
            db: Database session
            vector_store: VectorStore instance (creates new if None)
        """
        self.db = db
        self.vector_store = vector_store or VectorStore(use_incremental=True)
        
        # Load vector store if available
        if not self.vector_store.is_loaded():
            self.vector_store.load()

    def sync_change_log(
        self, change_log: ProductChangeLog
    ) -> Tuple[bool, Optional[str]]:
        """
        Sync a single change log record to vector store.
        
        State machine:
        - Success: status=PROCESSED
        - Failure: status=FAILED, retry_count+=1, last_error recorded
        - retry_count > MAX_VECTOR_RETRY: no automatic retry
        
        Args:
            change_log: ProductChangeLog record to sync
            
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        document_id = f"{change_log.brand_code}#{change_log.sku}"
        logger.info(
            f"[VECTOR_SYNC] Processing change_log: id={change_log.id}, "
            f"document_id={document_id}, change_type={change_log.change_type}, "
            f"status={change_log.status}, retry_count={change_log.retry_count}"
        )
        
        # Check retry limit
        if change_log.retry_count >= MAX_VECTOR_RETRY:
            logger.warning(
                f"[VECTOR_SYNC] Skipping {document_id}: retry_count={change_log.retry_count} "
                f">= MAX_VECTOR_RETRY={MAX_VECTOR_RETRY}"
            )
            return False, f"Retry count exceeded (>{MAX_VECTOR_RETRY})"
        
        try:
            # Handle DELETE change type
            if change_log.change_type == ChangeType.DELETE.value:
                # TODO: Implement delete from vector store if needed
                # For now, we skip DELETE (vector store will naturally exclude deleted products)
                logger.info(f"[VECTOR_SYNC] DELETE change_type for {document_id}, skipping")
                change_log.status = ChangeStatus.PROCESSED.value
                change_log.last_error = None
                self.db.commit()
                return True, None
            
            # Read latest product data
            product = get_product_by_brand_and_sku(
                self.db, change_log.brand_code, change_log.sku
            )
            
            if not product:
                error_msg = f"Product not found: brand_code={change_log.brand_code}, sku={change_log.sku}"
                logger.error(f"[VECTOR_SYNC] {error_msg}")
                self._mark_failed(change_log, error_msg)
                return False, error_msg
            
            # Build vector text
            vector_text = ProductVectorTextBuilder.build_vector_text(product)
            
            # Upsert to vector store
            success = self.vector_store.upsert_vector(document_id, vector_text)
            
            if not success:
                error_msg = f"Failed to upsert vector: document_id={document_id}"
                logger.error(f"[VECTOR_SYNC] {error_msg}")
                self._mark_failed(change_log, error_msg)
                return False, error_msg
            
            # Mark as processed
            change_log.status = ChangeStatus.PROCESSED.value
            change_log.last_error = None
            self.db.commit()
            
            logger.info(
                f"[VECTOR_SYNC] ✓ Successfully synced: document_id={document_id}, "
                f"change_log_id={change_log.id}"
            )
            
            return True, None
            
        except Exception as e:
            error_msg = f"Exception during sync: {type(e).__name__}: {str(e)}"
            logger.error(f"[VECTOR_SYNC] {error_msg}", exc_info=True)
            self._mark_failed(change_log, error_msg)
            return False, error_msg

    def sync_change_logs_batch(
        self, change_logs: List[ProductChangeLog]
    ) -> dict[str, int]:
        """
        Batch sync multiple change log records.
        
        Uses batch embedding generation for better performance.
        
        Args:
            change_logs: List of ProductChangeLog records to sync
            
        Returns:
            Statistics dictionary: {success, failed, skipped}
        """
        stats = {"success": 0, "failed": 0, "skipped": 0}
        
        if not change_logs:
            return stats
        
        logger.info(f"[VECTOR_SYNC] Batch syncing {len(change_logs)} change logs...")
        
        # Separate into upsert and delete batches
        upsert_logs: List[ProductChangeLog] = []
        delete_logs: List[ProductChangeLog] = []
        
        for log in change_logs:
            if log.retry_count >= MAX_VECTOR_RETRY:
                stats["skipped"] += 1
                continue
            
            if log.change_type == ChangeType.DELETE.value:
                delete_logs.append(log)
            else:
                upsert_logs.append(log)
        
        # Process DELETE logs (skip for now)
        for log in delete_logs:
            logger.info(
                f"[VECTOR_SYNC] DELETE change_type for {log.brand_code}#{log.sku}, skipping"
            )
            log.status = ChangeStatus.PROCESSED.value
            log.last_error = None
            stats["success"] += 1
        
        # Batch process UPSERT logs
        if upsert_logs:
            # Read products in batch
            document_texts: List[Tuple[str, str]] = []
            log_map: dict[str, ProductChangeLog] = {}
            
            for log in upsert_logs:
                product = get_product_by_brand_and_sku(
                    self.db, log.brand_code, log.sku
                )
                
                if not product:
                    error_msg = f"Product not found: {log.brand_code}#{log.sku}"
                    logger.error(f"[VECTOR_SYNC] {error_msg}")
                    self._mark_failed(log, error_msg)
                    stats["failed"] += 1
                    continue
                
                document_id = f"{log.brand_code}#{log.sku}"
                vector_text = ProductVectorTextBuilder.build_vector_text(product)
                document_texts.append((document_id, vector_text))
                log_map[document_id] = log
            
            # Batch upsert vectors
            if document_texts:
                results = self.vector_store.upsert_vectors_batch(document_texts)
                
                # Update change log statuses
                for document_id, success in results.items():
                    log = log_map[document_id]
                    if success:
                        log.status = ChangeStatus.PROCESSED.value
                        log.last_error = None
                        stats["success"] += 1
                    else:
                        error_msg = f"Batch upsert failed: document_id={document_id}"
                        self._mark_failed(log, error_msg)
                        stats["failed"] += 1
        
        # Commit all changes
        self.db.commit()
        
        # Save vector store
        self.vector_store.save()
        
        logger.info(
            f"[VECTOR_SYNC] Batch sync completed: "
            f"success={stats['success']}, failed={stats['failed']}, skipped={stats['skipped']}"
        )
        
        return stats

    def _mark_failed(self, change_log: ProductChangeLog, error_msg: str) -> None:
        """
        Mark change log as failed and increment retry count.
        
        Args:
            change_log: ProductChangeLog record
            error_msg: Error message (truncated to 1000 chars)
        """
        change_log.status = ChangeStatus.FAILED.value
        change_log.retry_count += 1
        change_log.last_error = error_msg[:1000]  # Truncate to 1000 chars
        self.db.commit()
        
        logger.warning(
            f"[VECTOR_SYNC] Marked as FAILED: change_log_id={change_log.id}, "
            f"retry_count={change_log.retry_count}, error={error_msg[:100]}"
        )


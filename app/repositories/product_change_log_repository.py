"""Product change log repository for querying pending changes."""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.product_change_log import ChangeStatus, ProductChangeLog

logger = logging.getLogger(__name__)


class ProductChangeLogRepository:
    """Repository for querying product change log records."""

    def __init__(self, db: Session):
        """
        Initialize repository.
        
        Args:
            db: Database session
        """
        self.db = db

    def fetch_pending_changes(
        self, limit: int = 1000, last_id: Optional[int] = None
    ) -> list[ProductChangeLog]:
        """
        Fetch pending change log records using cursor pagination.
        
        Uses cursor pagination (id > last_id) instead of offset to avoid
        performance issues with deep pagination.
        
        Args:
            limit: Maximum number of records to fetch
            last_id: Last processed ID (cursor for pagination)
            
        Returns:
            List of ProductChangeLog records with status='PENDING'
        """
        query = (
            self.db.query(ProductChangeLog)
            .filter(ProductChangeLog.status == ChangeStatus.PENDING.value)
        )
        
        # Cursor pagination: WHERE id > last_id
        if last_id is not None:
            query = query.filter(ProductChangeLog.id > last_id)
        
        # Order by id ASC for consistent pagination
        query = query.order_by(ProductChangeLog.id.asc()).limit(limit)
        
        records = query.all()
        
        logger.info(
            f"[CHANGE_LOG_REPO] Fetched {len(records)} pending changes "
            f"(last_id={last_id}, limit={limit})"
        )
        
        return records

    def get_max_id(self) -> Optional[int]:
        """
        Get the maximum ID from product_change_log table.
        
        Returns:
            Maximum ID, or None if table is empty
        """
        result = self.db.execute(
            text("SELECT MAX(id) as max_id FROM belle_ai.product_change_log")
        ).first()
        
        if result and result.max_id is not None:
            return int(result.max_id)
        
        return None


"""ETL watermark model for tracking processing progress."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ETLWatermark(Base):
    """ETL watermark model for tracking batch processing progress."""

    __tablename__ = "etl_watermark"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    table_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="表名，如 'products_staging'",
    )
    last_processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="最后处理时间（src_updated_at）",
    )
    last_processed_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="最后处理的组合键（style_brand_no#style_no），用于同秒不漏",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("table_name", name="uq_etl_watermark_table_name"),
        {"comment": "ETL 水位表，记录处理进度"},
    )

    def __repr__(self) -> str:
        return (
            f"<ETLWatermark(table_name='{self.table_name}', "
            f"last_processed_at={self.last_processed_at}, "
            f"last_processed_key='{self.last_processed_key}')>"
        )


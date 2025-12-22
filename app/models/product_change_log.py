"""Product change log model for tracking data changes."""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChangeType(str, Enum):
    """Change type enumeration."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ChangeStatus(str, Enum):
    """Change status enumeration."""

    PENDING = "PENDING"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"


class ProductChangeLog(Base):
    """Product change log model for tracking data version changes."""

    __tablename__ = "product_change_log"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="主键ID",
    )
    brand_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="品牌代码",
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="商品SKU",
    )
    data_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="数据版本哈希值",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ChangeStatus.PENDING.value,
        comment="状态：PENDING/PROCESSED/FAILED",
    )
    change_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="变更类型：CREATE/UPDATE/DELETE",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="重试次数",
    )
    last_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="最后错误信息",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint(
            "brand_code", "sku", "data_version", name="uq_change_log_brand_sku_version"
        ),
        {"comment": "商品变更日志表，记录数据版本变更"},
    )

    def __repr__(self) -> str:
        return (
            f"<ProductChangeLog(brand_code='{self.brand_code}', "
            f"sku='{self.sku}', data_version='{self.data_version}', "
            f"status='{self.status}', change_type='{self.change_type}')>"
        )


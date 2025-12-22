"""Product ORM model."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import DECIMAL

from app.core.database import Base


class Product(Base):
    """Product model representing shoe products."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="商品主键ID",
    )
    brand_code: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="品牌代码，与 sku 组成业务主键",
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="商品SKU编码，与 brand_code 组成业务主键",
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="商品名称",
    )
    price: Mapped[float] = mapped_column(
        DECIMAL(10, 2),
        nullable=False,
        comment="商品价格（元）",
    )
    tags: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="商品标签数组，如：[\"百搭\",\"舒适\",\"时尚\"]",
    )
    attributes: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
        comment="商品属性JSON，包含color/material/scene/season等",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="商品详细描述",
    )
    image_url: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        comment="商品主图URL",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="更新时间",
    )

    __table_args__ = (
        UniqueConstraint("brand_code", "sku", name="idx_products_brand_sku"),
        Index("idx_products_sku", "sku"),
        {"comment": "商品信息表"},
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, brand_code='{self.brand_code}', sku='{self.sku}', name='{self.name}')>"


"""Guide ORM model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Guide(Base):
    """Guide model representing sales guides."""

    __tablename__ = "guides"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="导购主键ID",
    )
    guide_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        comment="导购唯一标识ID",
    )
    name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="导购姓名",
    )
    shop_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        comment="所属门店名称",
    )
    level: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="导购等级：junior-初级, senior-高级, expert-专家",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )

    __table_args__ = ({"comment": "导购信息表"},)

    def __repr__(self) -> str:
        return f"<Guide(id={self.id}, guide_id='{self.guide_id}', name='{self.name}')>"


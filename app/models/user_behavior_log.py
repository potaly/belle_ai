"""User behavior log ORM model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserBehaviorLog(Base):
    """User behavior log model."""

    __tablename__ = "user_behavior_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
        comment="日志主键ID",
    )
    user_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="用户ID",
    )
    guide_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="导购ID",
    )
    sku: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="商品SKU",
    )
    event_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="事件类型：browse-浏览, enter_buy_page-进入购买页, click_size_chart-点击尺码表, favorite-收藏, share-分享",
    )
    stay_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="停留时长（秒）",
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        comment="事件发生时间",
    )

    __table_args__ = (
        Index(
            "idx_ubl_user_sku",
            "user_id",
            "sku",
            "occurred_at",
        ),
        Index(
            "idx_ubl_event_time",
            "event_type",
            "occurred_at",
        ),
        {"comment": "用户行为日志表"},
    )

    def __repr__(self) -> str:
        return (
            f"<UserBehaviorLog(id={self.id}, user_id='{self.user_id}', "
            f"event_type='{self.event_type}', sku='{self.sku}')>"
        )


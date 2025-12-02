"""AI task log ORM model."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AITaskLog(Base):
    """AI task log model."""

    __tablename__ = "ai_task_log"

    task_id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        comment="任务ID，唯一标识",
    )
    guide_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="导购ID",
    )
    scene_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="场景类型：copy-文案生成, product_analyze-商品分析, intent-意图分析",
    )
    input_data: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="输入数据（JSON格式）",
    )
    output_result: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="输出结果（JSON格式）",
    )
    model_name: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        comment="使用的模型名称",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="请求耗时（毫秒）",
    )
    is_adopted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否被采用：0-未采用, 1-已采用",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        comment="创建时间",
    )

    __table_args__ = (
        Index(
            "idx_ai_log_scene_time",
            "scene_type",
            "created_at",
        ),
        {"comment": "AI调用任务日志表"},
    )

    def __repr__(self) -> str:
        return (
            f"<AITaskLog(task_id='{self.task_id}', scene_type='{self.scene_type}', "
            f"guide_id='{self.guide_id}')>"
        )


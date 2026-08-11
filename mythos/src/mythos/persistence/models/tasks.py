from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow


class PlayerTaskState(Base):
    __tablename__ = "player_task_states"
    __table_args__ = (
        CheckConstraint("exception >= 0", name="ck_player_task_states_exception"),
        Index("ix_player_task_states_task_id", "task_id"),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    task_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    time_1: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    time_2: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exception: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    meta: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

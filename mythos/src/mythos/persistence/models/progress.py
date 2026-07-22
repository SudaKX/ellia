from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow

if TYPE_CHECKING:
    from mythos.persistence.models.player import PlayerRecord


class PlayerProgress(Base):
    __tablename__ = "player_progress"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_account: Mapped[str] = mapped_column(String(32), default="PLAYER", nullable=False)
    story_node: Mapped[str] = mapped_column(String(64), default="intro", nullable=False)
    checkpoint: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    player: Mapped[PlayerRecord] = relationship(back_populates="progress")

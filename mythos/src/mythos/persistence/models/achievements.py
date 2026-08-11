from __future__ import annotations

from datetime import datetime
from uuid import UUID
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow

if TYPE_CHECKING:
    from mythos.persistence.models.player import PlayerRecord


class PlayerAchievementState(Base):
    __tablename__ = "player_achievement_states"
    __table_args__ = (Index("ix_player_achievement_states_achievement_stable_id", "achievement_stable_id"),)

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    achievement_stable_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    player: Mapped["PlayerRecord"] = relationship(back_populates="achievements")

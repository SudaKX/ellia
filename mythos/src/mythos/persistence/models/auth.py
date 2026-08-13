from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base

if TYPE_CHECKING:
    from mythos.persistence.models.player import PlayerRecord


class PlayerAuth(Base):
    __tablename__ = "player_auth"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_selector: Mapped[str | None] = mapped_column(String(128), unique=True)
    refresh_secret_hash: Mapped[str | None] = mapped_column(String(128))
    refresh_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refresh_rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    player: Mapped[PlayerRecord] = relationship(back_populates="auth")

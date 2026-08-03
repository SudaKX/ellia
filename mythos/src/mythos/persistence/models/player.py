from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow

if TYPE_CHECKING:
    from mythos.persistence.models.auth import PlayerAuth
    from mythos.persistence.models.progress import PlayerProgress


class PlayerRecord(Base):
    __tablename__ = "players"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    constructed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    auth: Mapped[PlayerAuth] = relationship(back_populates="player", uselist=False)
    progress: Mapped[PlayerProgress] = relationship(back_populates="player", uselist=False)

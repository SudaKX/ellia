from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow


class PlayerHintDisclosure(Base):
    __tablename__ = "player_hint_disclosures"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hint_stable_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    disclosed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow


class PlayerCreditBalance(Base):
    __tablename__ = "player_credit_balances"
    __table_args__ = (
        CheckConstraint("balance >= 0", name="ck_player_credit_balances_balance"),
        CheckConstraint("version >= 0", name="ck_player_credit_balances_version"),
        Index("ix_player_credit_balances_credit_id", "credit_id"),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    credit_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class PlayerCreditState(Base):
    __tablename__ = "player_credit_states"
    __table_args__ = (
        CheckConstraint("version >= 0", name="ck_player_credit_states_version"),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

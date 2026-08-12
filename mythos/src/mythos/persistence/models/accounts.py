from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow


class PlayerVirtualAccount(Base):
    __tablename__ = "player_virtual_accounts"
    __table_args__ = (
        CheckConstraint("login_count >= 0", name="ck_player_virtual_accounts_login_count"),
        UniqueConstraint("player_id", "username_normalized", name="uq_player_virtual_accounts_username"),
        Index("ix_player_virtual_accounts_account_id", "account_id"),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    account_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    username: Mapped[str] = mapped_column(String(32), nullable=False)
    username_normalized: Mapped[str] = mapped_column(String(32), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_logged_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class PlayerVirtualAccountState(Base):
    __tablename__ = "player_virtual_account_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["player_id", "current_account_id"],
            ["player_virtual_accounts.player_id", "player_virtual_accounts.account_id"],
        ),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_account_id: Mapped[str | None] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

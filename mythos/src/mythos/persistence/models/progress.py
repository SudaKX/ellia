from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow

if TYPE_CHECKING:
    from mythos.persistence.models.player import PlayerRecord


class PlayerProgress(Base):
    __tablename__ = "player_progress"
    __table_args__ = (
        CheckConstraint(
            "current_checkpoint_sequence >= -1",
            name="ck_player_progress_current_checkpoint_sequence",
        ),
        CheckConstraint(
            "next_checkpoint_sequence >= 0",
            name="ck_player_progress_next_checkpoint_sequence",
        ),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("players.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_checkpoint_sequence: Mapped[int] = mapped_column(Integer, default=-1, nullable=False)
    next_checkpoint_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    player: Mapped[PlayerRecord] = relationship(back_populates="progress")
    unlocked_nodes: Mapped[list[PlayerProgressUnlockedNode]] = relationship(
        back_populates="progress",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    frontier_nodes: Mapped[list[PlayerProgressFrontierNode]] = relationship(
        back_populates="progress",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlayerProgressUnlockedNode(Base):
    __tablename__ = "player_progress_unlocked_nodes"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("player_progress.player_id", ondelete="CASCADE"),
        primary_key=True,
    )
    node_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    progress: Mapped[PlayerProgress] = relationship(back_populates="unlocked_nodes")


class PlayerProgressFrontierNode(Base):
    __tablename__ = "player_progress_frontier_nodes"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("player_progress.player_id", ondelete="CASCADE"),
        primary_key=True,
    )
    node_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    progress: Mapped[PlayerProgress] = relationship(back_populates="frontier_nodes")


class PlayerProgressCheckpoint(Base):
    __tablename__ = "player_progress_checkpoints"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("player_progress.player_id", ondelete="CASCADE"),
        primary_key=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

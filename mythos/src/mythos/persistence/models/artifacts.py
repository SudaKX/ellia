from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKeyConstraint, String
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from mythos.persistence.base import Base, utcnow


class PlayerArtifact(Base):
    __tablename__ = "player_artifacts"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    artifact_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    version: Mapped[str] = mapped_column(String(255), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(71), nullable=False)
    media_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    download_name: Mapped[str] = mapped_column(String(255), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    nodes: Mapped[list[PlayerArtifactNode]] = relationship(
        back_populates="artifact",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PlayerArtifactNode(Base):
    __tablename__ = "player_artifact_nodes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["player_id", "artifact_id"],
            ["player_artifacts.player_id", "player_artifacts.artifact_id"],
            ondelete="CASCADE",
        ),
    )

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    node_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    artifact_id: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    version: Mapped[str] = mapped_column(String(255), nullable=False)
    display: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    hidden: Mapped[bool] = mapped_column(default=False, nullable=False)
    download_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )

    artifact: Mapped[PlayerArtifact] = relationship(back_populates="nodes")


class PlayerArtifactState(Base):
    __tablename__ = "player_artifact_states"

    player_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
    )
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

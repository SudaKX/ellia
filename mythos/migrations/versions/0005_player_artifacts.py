"""Add player artifacts and artifact nodes.

Revision ID: 0005_player_artifacts
Revises: 0004_static_file_registrations
Create Date: 2026-07-30
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0005_player_artifacts"
down_revision: str | None = "0004_static_file_registrations"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_artifacts",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("artifact_id", sa.String(length=255), nullable=False),
        sa.Column("revision", sa.String(length=255), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("object_version_id", sa.String(length=1024), nullable=False),
        sa.Column("content_digest", sa.String(length=71), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("download_name", sa.String(length=255), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("player_id", "artifact_id"),
    )
    op.create_table(
        "player_artifact_nodes",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("node_id", sa.String(length=255), nullable=False),
        sa.Column("artifact_id", sa.String(length=255), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("revision", sa.String(length=255), nullable=False),
        sa.Column("display", sa.JSON(), nullable=False),
        sa.Column("hidden", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["player_id", "artifact_id"],
            ["player_artifacts.player_id", "player_artifacts.artifact_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("player_id", "node_id"),
    )


def downgrade() -> None:
    op.drop_table("player_artifact_nodes")
    op.drop_table("player_artifacts")

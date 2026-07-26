"""Add static file registrations.

Revision ID: 0004_static_file_registrations
Revises: 0003_remove_legacy_progress_fields
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0004_static_file_registrations"
down_revision: str | None = "0003_remove_legacy_progress_fields"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "static_file_registrations",
        sa.Column("source_locator", sa.String(length=512), nullable=False),
        sa.Column("source_mtime_ns", sa.BigInteger(), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("object_version_id", sa.String(length=1024), nullable=False),
        sa.Column("content_digest", sa.String(length=71), nullable=False),
        sa.Column("media_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("source_locator"),
    )


def downgrade() -> None:
    op.drop_table("static_file_registrations")

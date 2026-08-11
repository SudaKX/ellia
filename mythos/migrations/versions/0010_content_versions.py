"""Replace object versions with content hashes and persist node download overrides.

Revision ID: 0010_content_versions
Revises: 0009_player_credits_and_hints
Create Date: 2026-08-06
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010_content_versions"
down_revision: str | None = "0009_player_credits_and_hints"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("static_file_registrations") as batch:
        batch.drop_column("source_mtime_ns")
        batch.drop_column("object_version_id")
    with op.batch_alter_table("player_artifacts") as batch:
        batch.drop_column("object_version_id")
    with op.batch_alter_table("player_artifact_nodes") as batch:
        batch.add_column(sa.Column("download_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    raise RuntimeError(
        "0010_content_versions is irreversible because provider object version IDs were removed."
    )

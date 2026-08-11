"""Replace artifact revisions with computed template versions.

Revision ID: 0006_artifact_template_versions
Revises: 0005_player_artifacts
Create Date: 2026-08-01
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_artifact_template_versions"
down_revision: str | None = "0005_player_artifacts"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("player_artifacts") as batch:
        batch.add_column(sa.Column("version", sa.String(length=255), nullable=True))
    op.execute("UPDATE player_artifacts SET version = revision")
    with op.batch_alter_table("player_artifacts") as batch:
        batch.alter_column("version", nullable=False)
        batch.drop_column("revision")

    with op.batch_alter_table("player_artifact_nodes") as batch:
        batch.add_column(sa.Column("version", sa.String(length=255), nullable=True))
    op.execute("UPDATE player_artifact_nodes SET version = revision")
    with op.batch_alter_table("player_artifact_nodes") as batch:
        batch.alter_column("version", nullable=False)
        batch.drop_column("revision")

    op.create_table(
        "player_artifact_states",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("player_id"),
    )


def downgrade() -> None:
    op.drop_table("player_artifact_states")

    with op.batch_alter_table("player_artifact_nodes") as batch:
        batch.add_column(sa.Column("revision", sa.String(length=255), nullable=True))
    op.execute("UPDATE player_artifact_nodes SET revision = version")
    with op.batch_alter_table("player_artifact_nodes") as batch:
        batch.alter_column("revision", nullable=False)
        batch.drop_column("version")

    with op.batch_alter_table("player_artifacts") as batch:
        batch.add_column(sa.Column("revision", sa.String(length=255), nullable=True))
    op.execute("UPDATE player_artifacts SET revision = version")
    with op.batch_alter_table("player_artifacts") as batch:
        batch.alter_column("revision", nullable=False)
        batch.drop_column("version")

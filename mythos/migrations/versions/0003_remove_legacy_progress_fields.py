"""Remove legacy single-node progress fields.

Revision ID: 0003_remove_legacy_progress_fields
Revises: 0002_player_graph_progress
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_remove_legacy_progress_fields"
down_revision: str | None = "0002_player_graph_progress"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("player_progress") as batch:
        batch.drop_column("checkpoint")
        batch.drop_column("story_node")


def downgrade() -> None:
    with op.batch_alter_table("player_progress") as batch:
        batch.add_column(sa.Column("checkpoint", sa.String(length=64), nullable=True))
        batch.add_column(
            sa.Column("story_node", sa.String(length=64), nullable=False, server_default="intro")
        )

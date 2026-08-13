"""Add graph-backed player progress state.

Revision ID: 0002_player_graph_progress
Revises: 0001_initial_auth
Create Date: 2026-07-26
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0002_player_graph_progress"
down_revision: str | None = "0001_initial_auth"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("player_progress") as batch:
        batch.add_column(
            sa.Column("current_checkpoint_sequence", sa.Integer(), nullable=False, server_default="-1")
        )
        batch.add_column(
            sa.Column("next_checkpoint_sequence", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_check_constraint(
            "ck_player_progress_current_checkpoint_sequence",
            "current_checkpoint_sequence >= -1",
        )
        batch.create_check_constraint(
            "ck_player_progress_next_checkpoint_sequence",
            "next_checkpoint_sequence >= 0",
        )

    op.create_table(
        "player_progress_unlocked_nodes",
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.BigInteger(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["player_progress.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "node_id"),
    )
    op.create_table(
        "player_progress_frontier_nodes",
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("node_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["player_progress.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "node_id"),
    )
    op.create_table(
        "player_progress_checkpoints",
        sa.Column("player_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["player_progress.player_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "sequence"),
    )


def downgrade() -> None:
    op.drop_table("player_progress_checkpoints")
    op.drop_table("player_progress_frontier_nodes")
    op.drop_table("player_progress_unlocked_nodes")
    with op.batch_alter_table("player_progress") as batch:
        batch.drop_constraint("ck_player_progress_next_checkpoint_sequence", type_="check")
        batch.drop_constraint("ck_player_progress_current_checkpoint_sequence", type_="check")
        batch.drop_column("next_checkpoint_sequence")
        batch.drop_column("current_checkpoint_sequence")

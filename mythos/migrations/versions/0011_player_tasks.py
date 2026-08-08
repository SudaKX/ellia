"""Add lazy player task state.

Revision ID: 0011_player_tasks
Revises: 0010_content_versions
Create Date: 2026-08-08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0011_player_tasks"
down_revision: str | None = "0010_content_versions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_task_states",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("time_1", sa.DateTime(timezone=True), nullable=True),
        sa.Column("time_2", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exception", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("meta", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("exception >= 0", name="ck_player_task_states_exception"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "task_id"),
    )
    op.create_index(
        "ix_player_task_states_task_id",
        "player_task_states",
        ["task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_player_task_states_task_id", table_name="player_task_states")
    op.drop_table("player_task_states")

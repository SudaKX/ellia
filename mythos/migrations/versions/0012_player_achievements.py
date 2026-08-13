"""Add player achievement state.

Revision ID: 0012_player_achievements
Revises: 0011_player_tasks
Create Date: 2026-08-12
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0012_player_achievements"
down_revision: str | None = "0011_player_tasks"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_achievement_states",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("achievement_stable_id", sa.String(length=128), nullable=False),
        sa.Column("earned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "achievement_stable_id"),
    )
    op.create_index(
        "ix_player_achievement_states_achievement_stable_id",
        "player_achievement_states",
        ["achievement_stable_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_achievement_states_achievement_stable_id",
        table_name="player_achievement_states",
    )
    op.drop_table("player_achievement_states")

"""Add player credits and hint disclosures.

Revision ID: 0009_player_credits_and_hints
Revises: 0008_player_lifecycle
Create Date: 2026-08-04
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_player_credits_and_hints"
down_revision: str | None = "0008_player_lifecycle"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_credits",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("vtb", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("vtb >= 0", name="ck_player_credits_vtb"),
        sa.CheckConstraint("version >= 0", name="ck_player_credits_version"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id"),
    )
    op.execute(
        "INSERT INTO player_credits (player_id, vtb, version, updated_at) "
        "SELECT id, 0, 0, CURRENT_TIMESTAMP FROM players"
    )
    op.create_table(
        "player_hint_disclosures",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("hint_stable_id", sa.String(length=128), nullable=False),
        sa.Column("disclosed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "hint_stable_id"),
    )


def downgrade() -> None:
    op.drop_table("player_hint_disclosures")
    op.drop_table("player_credits")

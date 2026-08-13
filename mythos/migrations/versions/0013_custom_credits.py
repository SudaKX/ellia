"""Add custom player credit balances and aggregate state.

Revision ID: 0013_custom_credits
Revises: 0012_player_achievements
Create Date: 2026-08-13
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0013_custom_credits"
down_revision: str | None = "0012_player_achievements"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_credit_balances",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("credit_id", sa.String(length=128), nullable=False),
        sa.Column("balance", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_player_credit_balances_balance"),
        sa.CheckConstraint("version >= 0", name="ck_player_credit_balances_version"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "credit_id"),
    )
    op.create_index(
        "ix_player_credit_balances_credit_id",
        "player_credit_balances",
        ["credit_id"],
    )
    op.create_table(
        "player_credit_states",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("version >= 0", name="ck_player_credit_states_version"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id"),
    )
    op.execute(
        "INSERT INTO player_credit_balances (player_id, credit_id, balance, version, updated_at) "
        "SELECT player_id, 'vtb', vtb, version, updated_at FROM player_credits"
    )
    op.execute(
        "INSERT INTO player_credit_states (player_id, version) "
        "SELECT player_id, version FROM player_credits"
    )
    op.drop_table("player_credits")


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade of 0013_custom_credits is forbidden: restoring the player_credits wide "
        "table would discard non-VTB credit balances."
    )

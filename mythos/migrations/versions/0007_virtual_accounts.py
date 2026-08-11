"""Add player virtual accounts.

Revision ID: 0007_virtual_accounts
Revises: 0006_artifact_template_versions
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_virtual_accounts"
down_revision: str | None = "0006_artifact_template_versions"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "player_virtual_accounts",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("account_id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column("username_normalized", sa.String(length=32), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_logged_in_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("login_count >= 0", name="ck_player_virtual_accounts_login_count"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("player_id", "account_id"),
        sa.UniqueConstraint("player_id", "username_normalized", name="uq_player_virtual_accounts_username"),
    )
    op.create_index(
        "ix_player_virtual_accounts_account_id",
        "player_virtual_accounts",
        ["account_id"],
    )
    op.create_table(
        "player_virtual_account_states",
        sa.Column("player_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("current_account_id", sa.String(length=128), nullable=True),
        sa.Column("version", sa.BigInteger(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["player_id"], ["players.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["player_id", "current_account_id"],
            ["player_virtual_accounts.player_id", "player_virtual_accounts.account_id"],
        ),
        sa.PrimaryKeyConstraint("player_id"),
    )
    op.execute(
        "INSERT INTO player_virtual_account_states (player_id, current_account_id, version) "
        "SELECT id, NULL, 0 FROM players"
    )
    with op.batch_alter_table("player_progress") as batch:
        batch.drop_column("current_account")


def downgrade() -> None:
    with op.batch_alter_table("player_progress") as batch:
        batch.add_column(
            sa.Column(
                "current_account",
                sa.String(length=32),
                nullable=False,
                server_default="PLAYER",
            )
        )
    op.drop_table("player_virtual_account_states")
    op.drop_index("ix_player_virtual_accounts_account_id", table_name="player_virtual_accounts")
    op.drop_table("player_virtual_accounts")

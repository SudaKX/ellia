"""Track completed player construction.

Revision ID: 0008_player_lifecycle
Revises: 0007_virtual_accounts
Create Date: 2026-08-03
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_player_lifecycle"
down_revision: str | None = "0007_virtual_accounts"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("players") as batch:
        batch.add_column(sa.Column("constructed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("players") as batch:
        batch.drop_column("constructed_at")

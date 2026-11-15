"""m1 auth harden: sessions no longer keep the client address and browser (no reader).

Revision ID: ed6fa007a1fb
Revises: 86b81d6eb3e8
Create Date: 2026-11-12 21:20:03.769084
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ed6fa007a1fb"
down_revision: str | None = "86b81d6eb3e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("user_session", "user_agent")
    op.drop_column("user_session", "ip")


def downgrade() -> None:
    op.add_column("user_session", sa.Column("ip", sa.String(length=64), nullable=True))
    op.add_column("user_session", sa.Column("user_agent", sa.String(length=300), nullable=True))

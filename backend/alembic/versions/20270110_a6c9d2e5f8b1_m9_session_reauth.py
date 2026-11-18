"""m9 session reauth (plan M9 task 18, J9, ASVS 5.0 V7.5.1): a session opened by a
sign-in through a provider remembers when, so linking a new account within 10 minutes
needs no password.

Expand only: one new nullable column. The previous release (1.0.0) never names it.

Revision ID: a6c9d2e5f8b1
Revises: f2a5b8c3d6e9
Create Date: 2027-01-10 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a6c9d2e5f8b1"
down_revision: str | None = "f2a5b8c3d6e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_session", sa.Column("reauth_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("user_session", "reauth_at")

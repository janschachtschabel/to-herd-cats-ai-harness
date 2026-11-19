"""m9 fresh provider sign-in (review M9b Task 18, R18-10; ASVS 5.0 V7.5.1): a sign-in
started as the proof before linking asks the provider for a fresh login
(`prompt=login`, `max_age=600`); the flow remembers that it was one, and so does a
sign-in that then waits for the second factor.

Expand only: two new columns with a server default. The previous release (1.0.0) never
names them.

Revision ID: c8e1f4a7b0d3
Revises: b7d0e3f6a9c2
Create Date: 2027-01-12 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8e1f4a7b0d3"
down_revision: str | None = "b7d0e3f6a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("oidc_flow", "sign_in_challenge"):
        op.add_column(
            table,
            sa.Column("reauth", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    for table in ("oidc_flow", "sign_in_challenge"):
        op.drop_column(table, "reauth")

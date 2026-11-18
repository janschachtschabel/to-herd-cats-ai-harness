"""m9 oauth issuer (plan M9 task 18, J13, ASVS 5.0 V10.2.2): an OAuth app knows its
authorization server's issuer and whether that server sends `iss` in its authorization
responses (RFC 9207), so the callback can compare them.

Expand only: a nullable column and one with a server default. The previous release
(1.0.0) never names them.

Revision ID: b7d0e3f6a9c2
Revises: a6c9d2e5f8b1
Create Date: 2027-01-11 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d0e3f6a9c2"
down_revision: str | None = "a6c9d2e5f8b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("oauth_client", sa.Column("issuer", sa.String(500), nullable=True))
    op.add_column(
        "oauth_client",
        sa.Column("issuer_in_response", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("oauth_client", "issuer_in_response")
    op.drop_column("oauth_client", "issuer")

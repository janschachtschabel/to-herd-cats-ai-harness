"""m8 mcp catalogue (plan M8 task 9): `mcp_server.catalog_id` names the catalogue entry
a server was created from; its suggested classifications apply to the tools a refresh
adds.

Expand only: one new nullable column, which the previous release does not read.

Revision ID: a8d2f4b6c1e3
Revises: f4c6e8a0b2d4
Create Date: 2026-11-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8d2f4b6c1e3"
down_revision: str | None = "f4c6e8a0b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("mcp_server", sa.Column("catalog_id", sa.String(length=40), nullable=True))


def downgrade() -> None:
    op.drop_column("mcp_server", "catalog_id")

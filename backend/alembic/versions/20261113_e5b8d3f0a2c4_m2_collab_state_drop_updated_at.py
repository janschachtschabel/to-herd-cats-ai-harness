"""m2 collab state: drop updated_at, which no code read (review M2 R15).

M2 has not been released, so no running release writes the column.

Revision ID: e5b8d3f0a2c4
Revises: d4a7c2e91b3f
Create Date: 2026-11-13 08:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5b8d3f0a2c4"
down_revision: str | None = "d4a7c2e91b3f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("page_collab_state", "updated_at")


def downgrade() -> None:
    op.add_column(
        "page_collab_state",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

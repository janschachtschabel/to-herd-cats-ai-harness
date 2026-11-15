"""m8 personal release (module review M8 2, finding G2): `approval.personal` notes a
release asked because the run carries the personal mark (its card says so: what is
released is written where others read it).

Expand only: a column with a constant default (no rewrite). The previous release
neither reads nor writes it; its releases during a rollout have none.

Revision ID: 8e2a4c6b0d1f
Revises: 5b7d9f1a3c6e
Create Date: 2026-11-25 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8e2a4c6b0d1f"
down_revision: str | None = "5b7d9f1a3c6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "approval",
        sa.Column("personal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("approval", "personal")

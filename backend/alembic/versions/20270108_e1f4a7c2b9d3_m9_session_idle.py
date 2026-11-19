"""m9 session idle (plan M9 task 18, J7, ASVS 5.0 V7.3.1): a login session remembers
its last use, so it can end after HERD_SESSION_IDLE_HOURS without one.

Expand only: one new column with a server default. The previous release (1.0.0) never
names it; its new sessions get the time of their insert.

Revision ID: e1f4a7c2b9d3
Revises: daa60bc7c565
Create Date: 2027-01-08 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1f4a7c2b9d3"
down_revision: str | None = "daa60bc7c565"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_session",
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("user_session", "last_used_at")

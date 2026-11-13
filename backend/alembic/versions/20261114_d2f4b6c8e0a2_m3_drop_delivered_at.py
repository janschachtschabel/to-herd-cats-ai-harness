"""m3 drop delivered_at: `event_delivery.delivered_at` was written and read by no code
(hard rule 5, review M3 N14). Which handler had which event is all the dispatcher
reads.

Backward compatible with the previous release (M2), which has no outbox; no release
has written this column.

Revision ID: d2f4b6c8e0a2
Revises: c1e3a5b7d9f1
Create Date: 2026-11-14 09:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2f4b6c8e0a2"
down_revision: str | None = "c1e3a5b7d9f1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_column("event_delivery", "delivered_at")


def downgrade() -> None:
    op.add_column(
        "event_delivery",
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

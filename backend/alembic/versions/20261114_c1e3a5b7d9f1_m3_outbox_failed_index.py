"""m3 outbox failed index: a partial index over the events that gave up, so every
worker can count them for `herd_outbox_failed` on a timer without reading the table.

Backward compatible: an index only; the previous release does not use it.

Revision ID: c1e3a5b7d9f1
Revises: b9d1f3a5c7e9
Create Date: 2026-11-14 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1e3a5b7d9f1"
down_revision: str | None = "b9d1f3a5c7e9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_event_outbox_failed",
        "event_outbox",
        ["failed_at"],
        unique=False,
        postgresql_where=sa.text("failed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_event_outbox_failed", table_name="event_outbox")

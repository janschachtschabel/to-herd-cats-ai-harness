"""m9 drop outbox attempts: `event_outbox.attempts`, `next_attempt_at` and
`ix_event_outbox_due` belonged to the dispatcher of M4 (one pass over all handlers).
Since the lanes (migration b5d7f9a1c3e5) no code reads or writes them; they go now,
before the first release (plan M9 decision 22: a contraction after a release needs
`contract_of`). A worker older than the lanes must not run against this schema.

Revision ID: 5b8d2f6a9c13
Revises: 3d7f1b9c5e2a
Create Date: 2027-01-01 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b8d2f6a9c13"
down_revision: str | None = "3d7f1b9c5e2a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        "ix_event_outbox_due",
        table_name="event_outbox",
        postgresql_where=sa.text("dispatched_at IS NULL AND failed_at IS NULL"),
    )
    op.drop_column("event_outbox", "next_attempt_at")
    op.drop_column("event_outbox", "attempts")


def downgrade() -> None:
    op.add_column(
        "event_outbox",
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "event_outbox",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_event_outbox_due",
        "event_outbox",
        ["next_attempt_at"],
        unique=False,
        postgresql_where=sa.text("dispatched_at IS NULL AND failed_at IS NULL"),
    )

"""m4fix outbox lanes: one lane per handler (review M4 P3). The worker routes every new
event into one `event_lane` row per handler that wants it (`event_outbox.routed_at`);
each handler works off its own rows in batches, retries are counted per lane.

Backward compatible (expand only): a new table, a new nullable column and a partial
index. The previous release's workers ignore them and keep using
`event_outbox.attempts` / `next_attempt_at`; should both run during an update, the
delivery records keep every effect single. Those two columns and
`ix_event_outbox_due` are dropped in the next release.

Revision ID: b5d7f9a1c3e5
Revises: a3c5e7f9b1d3
Create Date: 2026-11-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b5d7f9a1c3e5"
down_revision: str | None = "a3c5e7f9b1d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("event_outbox", sa.Column("routed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_event_outbox_unrouted",
        "event_outbox",
        ["id"],
        unique=False,
        postgresql_where=sa.text(
            "routed_at IS NULL AND dispatched_at IS NULL AND failed_at IS NULL"
        ),
    )
    op.create_table(
        "event_lane",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handler", sa.String(length=100), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event_outbox.id"],
            name=op.f("fk_event_lane_event_id_event_outbox"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "handler", name=op.f("pk_event_lane")),
    )
    op.create_index(
        "ix_event_lane_due",
        "event_lane",
        ["handler", "event_id"],
        unique=False,
        postgresql_where=sa.text("failed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_event_lane_due", table_name="event_lane")
    op.drop_table("event_lane")
    op.drop_index("ix_event_outbox_unrouted", table_name="event_outbox")
    op.drop_column("event_outbox", "routed_at")

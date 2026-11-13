"""m3 outbox: the event outbox and the record of which handler has had which event.

Revision ID: a1c3e5f7b9d1
Revises: f6c9e4a1b3d5
Create Date: 2026-11-13 13:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1c3e5f7b9d1"
down_revision: str | None = "f6c9e4a1b3d5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "event_outbox",
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("space_id", sa.UUID(), nullable=True),
        sa.Column("subject_type", sa.String(length=32), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_event_outbox_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event_outbox")),
    )
    op.create_index(
        "ix_event_outbox_dispatched_at",
        "event_outbox",
        ["dispatched_at"],
        unique=False,
        postgresql_where=sa.text("dispatched_at IS NOT NULL"),
    )
    op.create_index(
        "ix_event_outbox_due",
        "event_outbox",
        ["next_attempt_at"],
        unique=False,
        postgresql_where=sa.text("dispatched_at IS NULL AND failed_at IS NULL"),
    )
    op.create_index(op.f("ix_event_outbox_org_id"), "event_outbox", ["org_id"], unique=False)
    op.create_table(
        "event_delivery",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("handler", sa.String(length=100), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event_outbox.id"],
            name=op.f("fk_event_delivery_event_id_event_outbox"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id", "handler", name=op.f("pk_event_delivery")),
    )


def downgrade() -> None:
    op.drop_table("event_delivery")
    op.drop_index(op.f("ix_event_outbox_org_id"), table_name="event_outbox")
    op.drop_index(
        "ix_event_outbox_due",
        table_name="event_outbox",
        postgresql_where=sa.text("dispatched_at IS NULL AND failed_at IS NULL"),
    )
    op.drop_index(
        "ix_event_outbox_dispatched_at",
        table_name="event_outbox",
        postgresql_where=sa.text("dispatched_at IS NOT NULL"),
    )
    op.drop_table("event_outbox")

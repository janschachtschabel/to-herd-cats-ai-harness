"""m10 events (plan M10 task 3a, decisions 3, 5 and 6): `calendar_event` (an event of
a calendar and its space, by the foreign key `(calendar_id, space_id)`; its series as
rule, RDATEs and EXDATEs in wall time, `recurs_until` for the window; overrides as
rows of their own; one live master per UID and calendar, a tombstone blocking
nothing: `NULLS NOT DISTINCT`, Postgres 15 or later) and `calendar.time_zone` (the
zone of a new event that names none; `Europe/Berlin` for existing rows).

Expand only: one new table and one new column with a server default. The previous
release (1.0.0) neither reads nor writes them.

Revision ID: c5e8a1d4f7b2
Revises: b1c4e7a90d23
Create Date: 2027-01-13 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c5e8a1d4f7b2"
down_revision: str | None = "b1c4e7a90d23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "calendar",
        sa.Column(
            "time_zone", sa.String(length=64), server_default="Europe/Berlin", nullable=False
        ),
    )
    op.create_table(
        "calendar_event",
        sa.Column("calendar_id", sa.UUID(), nullable=False),
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("uid", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("location", sa.String(length=500), server_default="", nullable=False),
        sa.Column("all_day", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tzid", sa.String(length=64), nullable=True),
        sa.Column("rrule", sa.String(length=500), nullable=True),
        sa.Column("rdates", postgresql.ARRAY(sa.DateTime()), server_default="{}", nullable=False),
        sa.Column("exdates", postgresql.ARRAY(sa.DateTime()), server_default="{}", nullable=False),
        sa.Column("recurs_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("series_id", sa.UUID(), nullable=True),
        sa.Column("recurrence_id", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("busy", sa.Boolean(), nullable=False),
        sa.Column("organizer_type", sa.String(length=16), nullable=False),
        sa.Column("organizer_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(series_id IS NULL) = (recurrence_id IS NULL)",
            name=op.f("ck_calendar_event_override"),
        ),
        sa.CheckConstraint("all_day = (tzid IS NULL)", name=op.f("ck_calendar_event_zone")),
        sa.CheckConstraint("ends_at >= starts_at", name=op.f("ck_calendar_event_times")),
        sa.CheckConstraint(
            "organizer_type IN ('user', 'agent')", name=op.f("ck_calendar_event_organizer_type")
        ),
        sa.CheckConstraint(
            "status IN ('confirmed', 'tentative', 'cancelled')",
            name=op.f("ck_calendar_event_status"),
        ),
        sa.CheckConstraint(
            "visibility IN ('default', 'private')", name=op.f("ck_calendar_event_visibility")
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id", "space_id"],
            ["calendar.id", "calendar.space_id"],
            name="fk_calendar_event_calendar_id_calendar",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_calendar_event_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["calendar_event.id"],
            name=op.f("fk_calendar_event_series_id_calendar_event"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_event")),
    )
    op.create_index(op.f("ix_calendar_event_org_id"), "calendar_event", ["org_id"], unique=False)
    op.create_index(
        "ix_calendar_event_organizer",
        "calendar_event",
        ["organizer_id", "starts_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_calendar_event_series_id", "calendar_event", ["series_id"], unique=False)
    op.create_index("ix_calendar_event_space_id", "calendar_event", ["space_id"], unique=False)
    op.create_index(
        "ix_calendar_event_window",
        "calendar_event",
        ["calendar_id", "starts_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_calendar_event_uid",
        "calendar_event",
        ["calendar_id", "uid", "recurrence_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
        postgresql_nulls_not_distinct=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_calendar_event_uid",
        table_name="calendar_event",
        postgresql_where=sa.text("deleted_at IS NULL"),
        postgresql_nulls_not_distinct=True,
    )
    op.drop_index(
        "ix_calendar_event_window",
        table_name="calendar_event",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index("ix_calendar_event_space_id", table_name="calendar_event")
    op.drop_index("ix_calendar_event_series_id", table_name="calendar_event")
    op.drop_index(
        "ix_calendar_event_organizer",
        table_name="calendar_event",
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.drop_index(op.f("ix_calendar_event_org_id"), table_name="calendar_event")
    op.drop_table("calendar_event")
    op.drop_column("calendar", "time_zone")

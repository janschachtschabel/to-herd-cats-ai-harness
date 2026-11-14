"""m7 event rules (plan M7 task 5, decisions 8 and 9).

- `event_outbox.run_id` (nullable, no foreign key): the run whose step caused the
  event.
- `automation.kind` admits `event`; `event_type`, `quiet_seconds` (60 to 86,400),
  `quiet_until`, `filter_tag_id`, `filter_ticket_kind`; an event rule has no time zone
  and is never `done`, and its `next_due_at` may be empty while it is active.
- `automation_firing.outcome` admits `skipped_depth`.
- `automation_event`: the events a rule took in, waiting for its quiet time's end or
  named by the term that took them.

Expand only: nullable columns, a new table, widened checks and new checks the
previous release's rows meet. The previous release never writes an event rule; it
claims one only while counted events wait (`next_due_at` set) and then fails in its
term computation, so the term stays due until a worker of this release fires it.

Revision ID: 5e2b9c7d4a18
Revises: c665b1a02d23
Create Date: 2026-11-14 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5e2b9c7d4a18"
down_revision: str | None = "c665b1a02d23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'once', 'recurring', 'heartbeat'"
OUTCOMES = (
    "'started', 'skipped_busy', 'skipped_paused_agent', 'skipped_budget', 'skipped_policy',"
    " 'skipped_off_hours'"
)
EVENT = (
    "(kind = 'event') = (event_type IS NOT NULL) AND "
    "(kind = 'event') = (quiet_seconds IS NOT NULL) AND "
    "(kind <> 'event' OR time_zone IS NULL) AND "
    "(kind = 'event' OR quiet_until IS NULL)"
)
EVENT_TYPES = "'page.published', 'ticket.created', 'attachment.uploaded', 'page.review_due'"


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column("event_outbox", sa.Column("run_id", sa.Uuid(), nullable=True))
    for name, kind in (
        ("event_type", sa.String(32)),
        ("quiet_seconds", sa.Integer()),
        ("quiet_until", sa.DateTime(timezone=True)),
        ("filter_tag_id", sa.Uuid()),
        ("filter_ticket_kind", sa.String(16)),
    ):
        op.add_column("automation", sa.Column(name, kind, nullable=True))
    _replace_check("automation", "kind", f"kind IN ({KINDS}, 'event')")
    _replace_check(
        "automation", "next_due", "kind = 'event' OR (state = 'done') = (next_due_at IS NULL)"
    )
    op.create_check_constraint(op.f("ck_automation_event"), "automation", EVENT)
    op.create_check_constraint(
        op.f("ck_automation_event_type"), "automation", f"event_type IN ({EVENT_TYPES})"
    )
    op.create_check_constraint(
        op.f("ck_automation_quiet_seconds"), "automation", "quiet_seconds BETWEEN 60 AND 86400"
    )
    op.create_check_constraint(
        op.f("ck_automation_event_filter"),
        "automation",
        "(filter_tag_id IS NULL AND filter_ticket_kind IS NULL) OR event_type = 'ticket.created'",
    )
    op.create_check_constraint(
        op.f("ck_automation_filter_ticket_kind"),
        "automation",
        "filter_ticket_kind IN ('epic', 'story', 'task', 'bug')",
    )
    op.create_index(
        "ix_automation_event_type",
        "automation",
        ["org_id", "event_type"],
        postgresql_where=sa.text("kind = 'event' AND state = 'active'"),
    )
    _replace_check("automation_firing", "outcome", f"outcome IN ({OUTCOMES}, 'skipped_depth')")
    op.create_table(
        "automation_event",
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("automation_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("firing_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name=op.f("fk_automation_event_automation_id_automation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["firing_id"],
            ["automation_firing.id"],
            name=op.f("fk_automation_event_firing_id_automation_firing"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_automation_event_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("automation_id", "event_id", name=op.f("pk_automation_event")),
    )
    op.create_index(
        "ix_automation_event_waiting",
        "automation_event",
        ["automation_id"],
        postgresql_where=sa.text("firing_id IS NULL"),
    )
    op.create_index("ix_automation_event_firing_id", "automation_event", ["firing_id"])
    op.create_index(op.f("ix_automation_event_org_id"), "automation_event", ["org_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_event_org_id"), table_name="automation_event")
    op.drop_index("ix_automation_event_firing_id", table_name="automation_event")
    op.drop_index("ix_automation_event_waiting", table_name="automation_event")
    op.drop_table("automation_event")
    op.execute("DELETE FROM automation_firing WHERE outcome = 'skipped_depth'")
    _replace_check("automation_firing", "outcome", f"outcome IN ({OUTCOMES})")
    op.execute("DELETE FROM automation WHERE kind = 'event'")
    op.drop_index("ix_automation_event_type", table_name="automation")
    for name in ("filter_ticket_kind", "event_filter", "quiet_seconds", "event_type", "event"):
        op.drop_constraint(op.f(f"ck_automation_{name}"), "automation", type_="check")
    _replace_check("automation", "next_due", "(state = 'done') = (next_due_at IS NULL)")
    _replace_check("automation", "kind", f"kind IN ({KINDS})")
    for name in (
        "filter_ticket_kind",
        "filter_tag_id",
        "quiet_until",
        "quiet_seconds",
        "event_type",
    ):
        op.drop_column("automation", name)
    op.drop_column("event_outbox", "run_id")

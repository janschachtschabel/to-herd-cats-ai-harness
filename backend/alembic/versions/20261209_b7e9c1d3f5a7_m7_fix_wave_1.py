"""m7 fix wave 1 (module review 1 of M7): what a term that cannot fire, an event
rule's run and the cleanup of waiting events need.

- `automation.term_errors`: terms in a row the due loop could not fire; each sets the
  automation aside for longer (finding 3), a logged term sets it back to 0.
- `automation_firing.event_type`, `event_count`, `event_objects`: what an event rule's
  started run is told (kind, how many, the newest objects' ids), copied as the term
  fires, so every take-up reads the same (finding 6).
- `automation_event.taken_at`: when the rule took the event in, so the cleanup can
  remove what a paused rule kept waiting too long (finding 11).

Expand only: new columns, nullable or with a default, and one check over the new
columns. The previous release writes none of them: its terms leave the event copy
empty (a run such a term started and this release takes up is told no events, only
its instruction, during the roll-out), its events get `taken_at` from the default,
and it never sets an automation aside.

Revision ID: b7e9c1d3f5a7
Revises: a3d5f7b9c1e2
Create Date: 2026-11-15 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b7e9c1d3f5a7"
down_revision: str | None = "a3d5f7b9c1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "automation",
        sa.Column("term_errors", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_automation_term_errors"), "automation", "term_errors >= 0")
    op.add_column("automation_firing", sa.Column("event_type", sa.String(32), nullable=True))
    op.add_column("automation_firing", sa.Column("event_count", sa.Integer(), nullable=True))
    op.add_column(
        "automation_firing",
        sa.Column("event_objects", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_automation_firing_event"),
        "automation_firing",
        "(event_type IS NULL) = (event_count IS NULL) AND "
        "(event_type IS NULL) = (event_objects IS NULL) AND "
        "(event_type IS NULL OR outcome = 'started')",
    )
    op.add_column(
        "automation_event",
        sa.Column(
            "taken_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("automation_event", "taken_at")
    op.drop_constraint(op.f("ck_automation_firing_event"), "automation_firing", type_="check")
    op.drop_column("automation_firing", "event_objects")
    op.drop_column("automation_firing", "event_count")
    op.drop_column("automation_firing", "event_type")
    op.drop_constraint(op.f("ck_automation_term_errors"), "automation", type_="check")
    op.drop_column("automation", "term_errors")

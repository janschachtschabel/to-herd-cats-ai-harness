"""m7 heartbeats (plan M7 task 4, decision 7): the kind `heartbeat` with its interval
and active hours, the log outcome `skipped_off_hours` and the log's mark
`heartbeat_ok` (the run answered `HEARTBEAT_OK`: nothing was delivered).

- `automation.kind` admits `heartbeat`; `interval_minutes` (15 to 1,440),
  `active_days` (ISO weekdays), `active_from`, `active_until` (local times), present
  exactly for a heartbeat, which also needs `time_zone`.
- `automation_firing.outcome` admits `skipped_off_hours`;
  `automation_firing.heartbeat_ok` (false by default) only on a `started` row.

Expand only: nullable columns, a column with a default, widened checks and new
checks the previous release's rows meet. The previous release never writes a
heartbeat; one it claims fails in its term computation and stays due (rolling
update note, `docs/AGENTEN.md`).

Revision ID: c665b1a02d23
Revises: d4f6b8a0c2e4
Create Date: 2026-11-14 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c665b1a02d23"
down_revision: str | None = "d4f6b8a0c2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = "'once', 'recurring'"
OUTCOMES = "'started', 'skipped_busy', 'skipped_paused_agent', 'skipped_budget', 'skipped_policy'"
HEARTBEAT = (
    "(kind = 'heartbeat') = (interval_minutes IS NOT NULL) AND "
    "(kind = 'heartbeat') = (active_days IS NOT NULL) AND "
    "(kind = 'heartbeat') = (active_from IS NOT NULL) AND "
    "(kind = 'heartbeat') = (active_until IS NOT NULL) AND "
    "(kind <> 'heartbeat' OR time_zone IS NOT NULL)"
)


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column("automation", sa.Column("interval_minutes", sa.Integer(), nullable=True))
    op.add_column(
        "automation",
        sa.Column("active_days", postgresql.ARRAY(sa.SmallInteger()), nullable=True),
    )
    op.add_column("automation", sa.Column("active_from", sa.Time(), nullable=True))
    op.add_column("automation", sa.Column("active_until", sa.Time(), nullable=True))
    _replace_check("automation", "kind", f"kind IN ({KINDS}, 'heartbeat')")
    op.create_check_constraint(op.f("ck_automation_heartbeat"), "automation", HEARTBEAT)
    op.create_check_constraint(
        op.f("ck_automation_interval_minutes"),
        "automation",
        "interval_minutes BETWEEN 15 AND 1440",
    )
    op.create_check_constraint(
        op.f("ck_automation_active_days"),
        "automation",
        "cardinality(active_days) BETWEEN 1 AND 7 AND "
        "active_days <@ ARRAY[1, 2, 3, 4, 5, 6, 7]::smallint[]",
    )
    _replace_check("automation_firing", "outcome", f"outcome IN ({OUTCOMES}, 'skipped_off_hours')")
    op.add_column(
        "automation_firing",
        sa.Column("heartbeat_ok", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_automation_firing_heartbeat_ok"),
        "automation_firing",
        "NOT heartbeat_ok OR outcome = 'started'",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("ck_automation_firing_heartbeat_ok"), "automation_firing", type_="check"
    )
    op.drop_column("automation_firing", "heartbeat_ok")
    op.execute("DELETE FROM automation_firing WHERE outcome = 'skipped_off_hours'")
    _replace_check("automation_firing", "outcome", f"outcome IN ({OUTCOMES})")
    op.execute("DELETE FROM automation WHERE kind = 'heartbeat'")
    op.drop_constraint(op.f("ck_automation_active_days"), "automation", type_="check")
    op.drop_constraint(op.f("ck_automation_interval_minutes"), "automation", type_="check")
    op.drop_constraint(op.f("ck_automation_heartbeat"), "automation", type_="check")
    _replace_check("automation", "kind", f"kind IN ({KINDS})")
    for column in ("active_until", "active_from", "active_days", "interval_minutes"):
        op.drop_column("automation", column)

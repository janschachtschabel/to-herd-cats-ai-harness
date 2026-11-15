"""m7 automation delete (plan M7 task 7): `automation.state` may be `deleted`, and a
deleted automation keeps whatever next term it had (or none).

Deleting through the API keeps the row, so its runs (`run.automation_id`, which
cascades), their journal and its log stay as history; nothing fires it again, since
the due loop and the event rules take only `active` ones.

Expand only: widened checks. The previous release never writes `deleted`; its due
loop and event rules pass a deleted automation over (they read `active` only), and
its activity view would still list an entry about one until its pods are replaced.

Revision ID: 8c4e1a7f3b26
Revises: 5e2b9c7d4a18
Create Date: 2026-11-15 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "8c4e1a7f3b26"
down_revision: str | None = "5e2b9c7d4a18"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

STATES = "'active', 'paused', 'done'"


def _replace_check(name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_automation_{name}"), "automation", type_="check")
    op.create_check_constraint(op.f(f"ck_automation_{name}"), "automation", condition)


def upgrade() -> None:
    _replace_check("state", f"state IN ({STATES}, 'deleted')")
    _replace_check(
        "next_due",
        "kind = 'event' OR state = 'deleted' OR (state = 'done') = (next_due_at IS NULL)",
    )


def downgrade() -> None:
    op.execute("DELETE FROM automation WHERE state = 'deleted'")
    _replace_check("next_due", "kind = 'event' OR (state = 'done') = (next_due_at IS NULL)")
    _replace_check("state", f"state IN ({STATES})")

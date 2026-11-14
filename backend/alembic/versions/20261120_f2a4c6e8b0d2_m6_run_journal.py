"""m6 run journal: runs that wait (`waiting` until `wait_until`), take-ups after a
lost lease counted apart (`recoveries`), one active run per conversation (running or
waiting), the new stop reasons `cancelled` and `waiting_timeout`, and
`run_cancel_request` (plan M6 task 1, decision 1).

Backward compatible: new nullable or defaulted columns, wider checks and new indexes
that every row of the previous release meets (it never writes `waiting`, so the new
active index holds what its running index held). `run_event` keeps its key (run,
attempt, step): the journal counts its steps on across take-ups, which that key
allows.

Revision ID: f2a4c6e8b0d2
Revises: e1b3d5f7a9c0
Create Date: 2026-11-20 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a4c6e8b0d2"
down_revision: str | None = "e1b3d5f7a9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_REASONS = (
    "'completed', 'max_steps', 'deadline', 'no_progress', 'rights_revoked', "
    "'policy_blocked', 'provider_refused', 'error'"
)
NEW_REASONS = OLD_REASONS + ", 'cancelled', 'waiting_timeout'"


def _stop_reason(reasons: str) -> str:
    return (
        "(state = 'done') = (stop_reason IS NOT NULL) AND "
        f"(stop_reason IS NULL OR stop_reason IN ({reasons}))"
    )


def upgrade() -> None:
    op.add_column("run", sa.Column("recoveries", sa.Integer(), server_default="0", nullable=False))
    op.add_column("run", sa.Column("wait_until", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint(op.f("ck_run_state"), "run", type_="check")
    op.create_check_constraint(
        op.f("ck_run_state"), "run", "state IN ('queued', 'running', 'waiting', 'done')"
    )
    op.drop_constraint(op.f("ck_run_stop_reason"), "run", type_="check")
    op.create_check_constraint(op.f("ck_run_stop_reason"), "run", _stop_reason(NEW_REASONS))
    op.create_check_constraint(
        op.f("ck_run_wait"), "run", "(state = 'waiting') = (wait_until IS NOT NULL)"
    )
    op.create_index(
        "uq_run_active_per_conversation",
        "run",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("state IN ('running', 'waiting')"),
    )
    op.create_index(
        "ix_run_waiting",
        "run",
        ["wait_until"],
        unique=False,
        postgresql_where=sa.text("state = 'waiting'"),
    )
    op.create_table(
        "run_cancel_request",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_run_cancel_request_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["app_user.id"],
            name=op.f("fk_run_cancel_request_requested_by_app_user"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["run.id"],
            name=op.f("fk_run_cancel_request_run_id_run"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("run_id", name=op.f("pk_run_cancel_request")),
    )
    op.create_index(
        op.f("ix_run_cancel_request_org_id"), "run_cancel_request", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_run_cancel_request_org_id"), table_name="run_cancel_request")
    op.drop_table("run_cancel_request")
    # Waiting runs and the new stop reasons do not exist before: end them as errors.
    op.execute(
        "UPDATE run SET state = 'done', stop_reason = 'error', wait_until = NULL, "
        "finished_at = now() WHERE state = 'waiting'"
    )
    op.execute(
        "UPDATE run SET stop_reason = 'error' WHERE stop_reason IN ('cancelled', 'waiting_timeout')"
    )
    op.drop_index("ix_run_waiting", table_name="run", postgresql_where=sa.text("state = 'waiting'"))
    op.drop_index(
        "uq_run_active_per_conversation",
        table_name="run",
        postgresql_where=sa.text("state IN ('running', 'waiting')"),
    )
    op.drop_constraint(op.f("ck_run_wait"), "run", type_="check")
    op.drop_constraint(op.f("ck_run_stop_reason"), "run", type_="check")
    op.create_check_constraint(op.f("ck_run_stop_reason"), "run", _stop_reason(OLD_REASONS))
    op.drop_constraint(op.f("ck_run_state"), "run", type_="check")
    op.create_check_constraint(
        op.f("ck_run_state"), "run", "state IN ('queued', 'running', 'done')"
    )
    op.drop_column("run", "wait_until")
    op.drop_column("run", "recoveries")

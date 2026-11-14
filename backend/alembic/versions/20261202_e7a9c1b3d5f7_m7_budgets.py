"""m7 budgets (plan M7 task 1, decision 10): `ai_budget`, a daily limit in tokens
and/or EUR for the organisation, a person or an agent; the index for an agent's usage
per day (the organisation's and a person's exist); the stop reason `budget`.

Expand only: a new table, a new index, the check on `run.stop_reason` admits one more
value; no row is rewritten. A pod of the previous release never writes `budget`; one
that reads such a run (run view, run list) fails on it until it is replaced, as with
the other values new in a release (`docs/AGENTEN.md`, Rolling Update).

Revision ID: e7a9c1b3d5f7
Revises: b7d9f1a3c5e7
Create Date: 2026-11-14 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7a9c1b3d5f7"
down_revision: str | None = "b7d9f1a3c5e7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

REASONS = (
    "'completed', 'max_steps', 'deadline', 'no_progress', 'rights_revoked', "
    "'policy_blocked', 'provider_refused', 'error', 'cancelled', 'waiting_timeout', "
    "'approval_expired'"
)


def _stop_reason(reasons: str) -> str:
    return (
        "(state = 'done') = (stop_reason IS NOT NULL) AND "
        f"(stop_reason IS NULL OR stop_reason IN ({reasons}))"
    )


def _replace_stop_reason(reasons: str) -> None:
    op.drop_constraint(op.f("ck_run_stop_reason"), "run", type_="check")
    op.create_check_constraint(op.f("ck_run_stop_reason"), "run", _stop_reason(reasons))


def upgrade() -> None:
    op.create_table(
        "ai_budget",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("tokens_per_day", sa.BigInteger(), nullable=True),
        sa.Column("cost_per_day", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(user_id, agent_id) <= 1", name=op.f("ck_ai_budget_subject")
        ),
        sa.CheckConstraint(
            "tokens_per_day IS NOT NULL OR cost_per_day IS NOT NULL",
            name=op.f("ck_ai_budget_limit"),
        ),
        sa.CheckConstraint(
            "tokens_per_day IS NULL OR tokens_per_day > 0",
            name=op.f("ck_ai_budget_tokens_per_day"),
        ),
        sa.CheckConstraint(
            "cost_per_day IS NULL OR cost_per_day > 0", name=op.f("ck_ai_budget_cost_per_day")
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent.id"], name=op.f("fk_ai_budget_agent_id_agent"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_ai_budget_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_ai_budget_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_budget")),
    )
    op.create_index(op.f("ix_ai_budget_org_id"), "ai_budget", ["org_id"], unique=False)
    op.create_index(
        "uq_ai_budget_organisation",
        "ai_budget",
        ["org_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NULL AND agent_id IS NULL"),
    )
    op.create_index(
        "uq_ai_budget_user",
        "ai_budget",
        ["org_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("user_id IS NOT NULL"),
    )
    op.create_index(
        "uq_ai_budget_agent",
        "ai_budget",
        ["org_id", "agent_id"],
        unique=True,
        postgresql_where=sa.text("agent_id IS NOT NULL"),
    )
    op.create_index(
        "ix_usage_record_agent_id_created_at",
        "usage_record",
        ["agent_id", "created_at"],
        unique=False,
    )
    _replace_stop_reason(REASONS + ", 'budget'")


def downgrade() -> None:
    op.execute("UPDATE run SET stop_reason = 'error' WHERE stop_reason = 'budget'")
    _replace_stop_reason(REASONS)
    op.drop_index("ix_usage_record_agent_id_created_at", table_name="usage_record")
    op.drop_index("uq_ai_budget_agent", table_name="ai_budget")
    op.drop_index("uq_ai_budget_user", table_name="ai_budget")
    op.drop_index("uq_ai_budget_organisation", table_name="ai_budget")
    op.drop_index(op.f("ix_ai_budget_org_id"), table_name="ai_budget")
    op.drop_table("ai_budget")

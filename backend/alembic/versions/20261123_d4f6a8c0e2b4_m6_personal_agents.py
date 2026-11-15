"""m6 personal agents (plan M6 task 10, decision 13): `agent.owner_user_id` (a personal
agent's owner; NULL for the organisation's agents), the organisation's switch
`ai_org_assignment.personal_agents` (on by default) and a daily unique index for the
audit entry `agent.admin_access` (an admin opened someone else's personal agent).

Backward compatible: a nullable column, a column with a default and an index; the
previous release writes agents without an owner (organisation agents) and org rows
that take the default.

Revision ID: d4f6a8c0e2b4
Revises: c7e9a1b3d5f8
Create Date: 2026-11-23 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6a8c0e2b4"
down_revision: str | None = "c7e9a1b3d5f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent", sa.Column("owner_user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_agent_owner_user_id_app_user"), "agent", "app_user", ["owner_user_id"], ["id"]
    )
    op.create_index("ix_agent_owner_user_id", "agent", ["owner_user_id"], unique=False)
    op.add_column(
        "ai_org_assignment",
        sa.Column("personal_agents", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index(
        "uq_audit_log_agent_admin_access_daily",
        "audit_log",
        ["actor_id", "target_id", sa.literal_column("((created_at AT TIME ZONE 'UTC')::date)")],
        unique=True,
        postgresql_where=sa.text("action = 'agent.admin_access'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_audit_log_agent_admin_access_daily",
        table_name="audit_log",
        postgresql_where=sa.text("action = 'agent.admin_access'"),
    )
    op.drop_column("ai_org_assignment", "personal_agents")
    op.drop_index("ix_agent_owner_user_id", table_name="agent")
    op.drop_constraint(op.f("fk_agent_owner_user_id_app_user"), "agent", type_="foreignkey")
    op.drop_column("agent", "owner_user_id")

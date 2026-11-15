"""m6 tool grants: an agent's autonomy level (`agent.level`, 1 to 3) and its entries
per tool (`agent_tool`: allow, confirm, block; plan M6 task 2, decision 2).

Agents that exist already were built to read only (M5): they become level 1. New
agents default to level 2 (spec 8.2), also those the previous release creates during
a rollout (the column's default).

Backward compatible: a new column with a default and a new table; the previous release
reads neither.

Revision ID: a3b5d7f9c1e3
Revises: f2a4c6e8b0d2
Create Date: 2026-11-20 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3b5d7f9c1e3"
down_revision: str | None = "f2a4c6e8b0d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent", sa.Column("level", sa.Integer(), server_default="1", nullable=False))
    op.alter_column("agent", "level", server_default="2")
    op.create_check_constraint(op.f("ck_agent_level"), "agent", "level BETWEEN 1 AND 3")
    op.create_table(
        "agent_tool",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("policy", sa.String(length=16), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "policy IN ('allow', 'confirm', 'block')", name=op.f("ck_agent_tool_policy")
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_tool_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_agent_tool_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_id", "tool", name=op.f("pk_agent_tool")),
    )
    op.create_index(op.f("ix_agent_tool_org_id"), "agent_tool", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_tool_org_id"), table_name="agent_tool")
    op.drop_table("agent_tool")
    op.drop_constraint(op.f("ck_agent_level"), "agent", type_="check")
    op.drop_column("agent", "level")

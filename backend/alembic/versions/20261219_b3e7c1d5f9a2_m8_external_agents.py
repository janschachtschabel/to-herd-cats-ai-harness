"""m8 external agents (plan M8 task 4, decisions 11 and 12): an agent has a `kind`,
`internal` (run by the worker) or `external` (works from outside through `/mcp`, with
no connection and no model, never personal, level 2 at most); an access token of kind
`agent` names its external agent (`agent_id`).

Expand only: `agent.kind` comes with the default `internal`, so every row the previous
release wrote (and writes) is internal; `connection_id` and `model` lose NOT NULL, a
check keeps them set for internal agents. `access_token.agent_id` is nullable; the
previous release writes personal tokens only, which the new check requires to have
none.

Revision ID: b3e7c1d5f9a2
Revises: f4c6e8a0b2d3
Create Date: 2026-11-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b3e7c1d5f9a2"
down_revision: str | None = "f4c6e8a0b2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "agent",
        sa.Column("kind", sa.String(length=16), nullable=False, server_default="internal"),
    )
    op.create_check_constraint(op.f("ck_agent_kind"), "agent", "kind IN ('internal', 'external')")
    op.alter_column("agent", "connection_id", nullable=True)
    op.alter_column("agent", "model", nullable=True)
    op.create_check_constraint(
        op.f("ck_agent_internal_target"),
        "agent",
        "kind = 'external' OR (connection_id IS NOT NULL AND model IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_agent_external_fields"),
        "agent",
        "kind = 'internal' OR (connection_id IS NULL AND model IS NULL"
        " AND owner_user_id IS NULL AND level <= 2)",
    )
    op.add_column(
        "access_token", sa.Column("agent_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_access_token_agent_id_agent"),
        "access_token",
        "agent",
        ["agent_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_access_token_agent_id"), "access_token", ["agent_id"])
    op.create_check_constraint(
        op.f("ck_access_token_agent"), "access_token", "(kind = 'agent') = (agent_id IS NOT NULL)"
    )


def downgrade() -> None:
    op.execute("DELETE FROM access_token WHERE kind = 'agent'")
    op.drop_constraint(op.f("ck_access_token_agent"), "access_token", type_="check")
    op.drop_index(op.f("ix_access_token_agent_id"), table_name="access_token")
    op.drop_constraint(op.f("fk_access_token_agent_id_agent"), "access_token", type_="foreignkey")
    op.drop_column("access_token", "agent_id")
    op.execute("DELETE FROM agent WHERE kind = 'external'")
    op.drop_constraint(op.f("ck_agent_external_fields"), "agent", type_="check")
    op.drop_constraint(op.f("ck_agent_internal_target"), "agent", type_="check")
    op.alter_column("agent", "model", nullable=False)
    op.alter_column("agent", "connection_id", nullable=False)
    op.drop_constraint(op.f("ck_agent_kind"), "agent", type_="check")
    op.drop_column("agent", "kind")

"""m5 agents and runs: agents as principals (`agent`), their runs (`run`,
`run_event`), the request window per connection (`ai_rate_window`); agents as space
members and DM participants; `agent` messages (an agent's answer) and `system`
messages in a DM with an agent (why a run stopped).

The message trigger function is replaced: `system` messages are taken in page and
ticket threads and in a DM an agent takes part in; `agent` messages only in a DM the
author agent takes part in.

Backward compatible: new tables, wider checks and a wider trigger that every row of
the previous release meets. The previous release lists DM participants by joining
people (an agent participant is left out there) and never writes the new kinds.

Revision ID: d9f1a3c5e7b9
Revises: e0a2c4e6f8b1
Create Date: 2026-11-18 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

MESSAGE_PLACE = """
CREATE OR REPLACE FUNCTION herd_message_system_only_in_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'system' AND NOT EXISTS (
        SELECT 1 FROM conversation
        WHERE id = NEW.conversation_id AND kind IN ('thread_page', 'thread_ticket')
    ) AND NOT EXISTS (
        SELECT 1 FROM conversation_participant
        WHERE conversation_id = NEW.conversation_id AND principal_type = 'agent'
    ) THEN
        RAISE EXCEPTION 'system_message_outside_thread' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.kind = 'agent' AND NOT EXISTS (
        SELECT 1 FROM conversation_participant
        WHERE conversation_id = NEW.conversation_id AND principal_type = 'agent'
          AND principal_id = NEW.author_id
    ) THEN
        RAISE EXCEPTION 'agent_message_outside_its_dm' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

PREVIOUS_MESSAGE_PLACE = """
CREATE OR REPLACE FUNCTION herd_message_system_only_in_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'system' AND NOT EXISTS (
        SELECT 1 FROM conversation
        WHERE id = NEW.conversation_id AND kind IN ('thread_page', 'thread_ticket')
    ) THEN
        RAISE EXCEPTION 'system_message_outside_thread' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

AUTHOR = (
    "(kind = 'system') = (author_type = 'system')"
    " AND (author_type = 'system') = (author_id IS NULL)"
)


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


revision: str = "d9f1a3c5e7b9"
down_revision: str | None = "e0a2c4e6f8b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("intro", sa.String(length=500), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("responsible_user_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("max_runtime_seconds", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'active', 'paused')", name=op.f("ck_agent_status")),
        sa.CheckConstraint("char_length(instructions) <= 20000", name=op.f("ck_agent_instr")),
        sa.CheckConstraint(
            "max_runtime_seconds BETWEEN 10 AND 600", name=op.f("ck_agent_max_runtime")
        ),
        sa.CheckConstraint("max_steps BETWEEN 1 AND 25", name=op.f("ck_agent_max_steps")),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["ai_connection.id"],
            name=op.f("fk_agent_connection_id_ai_connection"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_agent_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["responsible_user_id"],
            ["app_user.id"],
            name=op.f("fk_agent_responsible_user_id_app_user"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent")),
    )
    op.create_index("ix_agent_connection_id", "agent", ["connection_id"], unique=False)
    op.create_index(op.f("ix_agent_org_id"), "agent", ["org_id"], unique=False)
    op.create_table(
        "ai_rate_window",
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calls", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["ai_connection.id"],
            name=op.f("fk_ai_rate_window_connection_id_ai_connection"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_ai_rate_window_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("connection_id", name=op.f("pk_ai_rate_window")),
    )
    op.create_index(op.f("ix_ai_rate_window_org_id"), "ai_rate_window", ["org_id"], unique=False)
    op.create_table(
        "run",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("trigger_message_id", sa.UUID(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("stop_reason", sa.String(length=32), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("steps", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(state = 'done') = (stop_reason IS NOT NULL) AND (stop_reason IS NULL OR stop_reason IN ('completed', 'max_steps', 'deadline', 'no_progress', 'rights_revoked', 'policy_blocked', 'provider_refused', 'error'))",
            name=op.f("ck_run_stop_reason"),
        ),
        sa.CheckConstraint(
            "(state = 'running') = (lease_until IS NOT NULL)", name=op.f("ck_run_lease")
        ),
        sa.CheckConstraint("state IN ('queued', 'running', 'done')", name=op.f("ck_run_state")),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agent.id"], name=op.f("fk_run_agent_id_agent"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_run_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_run_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["trigger_message_id"],
            ["message.id"],
            name=op.f("fk_run_trigger_message_id_message"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name=op.f("fk_run_user_id_app_user")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run")),
    )
    op.create_index("ix_run_agent_id", "run", ["agent_id"], unique=False)
    op.create_index(
        "ix_run_open",
        "run",
        ["created_at"],
        unique=False,
        postgresql_where=sa.text("state <> 'done'"),
    )
    op.create_index(op.f("ix_run_org_id"), "run", ["org_id"], unique=False)
    op.create_index("ix_run_trigger_message_id", "run", ["trigger_message_id"], unique=False)
    op.create_index(
        "uq_run_queued_per_conversation",
        "run",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("state = 'queued'"),
    )
    op.create_index(
        "uq_run_running_per_conversation",
        "run",
        ["conversation_id"],
        unique=True,
        postgresql_where=sa.text("state = 'running'"),
    )
    op.create_table(
        "run_event",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "kind IN ('model_call', 'tool_call', 'stop')", name=op.f("ck_run_event_kind")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_run_event_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["run.id"], name=op.f("fk_run_event_run_id_run"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_run_event")),
    )
    op.create_index(op.f("ix_run_event_org_id"), "run_event", ["org_id"], unique=False)
    op.create_index("uq_run_event_step", "run_event", ["run_id", "attempt", "seq"], unique=True)
    _replace_check(
        "conversation_participant", "principal_type", "principal_type IN ('user', 'agent')"
    )
    _replace_check("space_member", "member_type", "member_type IN ('user', 'group', 'agent')")
    _replace_check("message", "kind", "kind IN ('human', 'system', 'agent')")
    _replace_check("message", "author_type", "author_type IN ('user', 'system', 'agent')")
    _replace_check("message", "author", AUTHOR + " AND (kind = 'agent') = (author_type = 'agent')")
    op.create_check_constraint(
        op.f("ck_message_agent_run"), "message", "kind <> 'agent' OR client_id IS NOT NULL"
    )
    op.execute(sa.text(MESSAGE_PLACE))


def downgrade() -> None:
    op.execute(sa.text(PREVIOUS_MESSAGE_PLACE))
    op.execute(
        "DELETE FROM conversation WHERE id IN (SELECT conversation_id FROM"
        " conversation_participant WHERE principal_type = 'agent')"
    )
    op.execute("DELETE FROM space_member WHERE member_type = 'agent'")
    op.drop_constraint(op.f("ck_message_agent_run"), "message", type_="check")
    _replace_check("message", "author", AUTHOR)
    _replace_check("message", "author_type", "author_type IN ('user', 'system')")
    _replace_check("message", "kind", "kind IN ('human', 'system')")
    _replace_check("space_member", "member_type", "member_type IN ('user', 'group')")
    _replace_check("conversation_participant", "principal_type", "principal_type IN ('user')")
    op.drop_index("uq_run_event_step", table_name="run_event")
    op.drop_index(op.f("ix_run_event_org_id"), table_name="run_event")
    op.drop_table("run_event")
    op.drop_index(
        "uq_run_running_per_conversation",
        table_name="run",
        postgresql_where=sa.text("state = 'running'"),
    )
    op.drop_index(
        "uq_run_queued_per_conversation",
        table_name="run",
        postgresql_where=sa.text("state = 'queued'"),
    )
    op.drop_index("ix_run_trigger_message_id", table_name="run")
    op.drop_index(op.f("ix_run_org_id"), table_name="run")
    op.drop_index("ix_run_open", table_name="run", postgresql_where=sa.text("state <> 'done'"))
    op.drop_index("ix_run_agent_id", table_name="run")
    op.drop_table("run")
    op.drop_index(op.f("ix_ai_rate_window_org_id"), table_name="ai_rate_window")
    op.drop_table("ai_rate_window")
    op.drop_index(op.f("ix_agent_org_id"), table_name="agent")
    op.drop_index("ix_agent_connection_id", table_name="agent")
    op.drop_table("agent")

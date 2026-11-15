"""m6 approvals (plan M6 task 7): `approval` (a tool call waiting for a person's
release, bound to a fingerprint) and `run_question` (`ask_user`'s question); message
kinds `approval` and `question` (a run's cards, written for its agent like `agent`
messages), notification reasons `approval` and `question`, and the stop reason
`approval_expired`.

The message trigger function is replaced: a card is taken where an `agent` message
is.

Expand only: new tables, CHECKs widened, a wider trigger. The previous release never
writes the new values; it meets them only once this release wrote them (rolling
update note, docs).

Revision ID: e860d4fcc724
Revises: 17c1453c21e1
Create Date: 2026-11-14 16:00:00.000000
"""

from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e860d4fcc724"
down_revision: str | None = "17c1453c21e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AGENT_KINDS = "('agent', 'approval', 'question')"

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
    IF NEW.kind IN {kinds} AND NOT EXISTS (
        SELECT 1 FROM conversation_participant
        WHERE conversation_id = NEW.conversation_id AND principal_type = 'agent'
          AND principal_id = NEW.author_id
    ) AND NOT EXISTS (
        SELECT 1 FROM conversation c
        JOIN space_member m ON m.space_id = c.space_id
        WHERE c.id = NEW.conversation_id
          AND c.kind IN ('channel', 'thread_page', 'thread_ticket')
          AND m.member_type = 'agent' AND m.member_id = NEW.author_id
    ) THEN
        RAISE EXCEPTION 'agent_message_outside_its_places' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

AUTHOR = (
    "(kind = 'system') = (author_type = 'system')"
    " AND (author_type = 'system') = (author_id IS NULL)"
    " AND ({agent}) = (author_type = 'agent')"
)
REASONS = (
    "'completed', 'max_steps', 'deadline', 'no_progress', 'rights_revoked', "
    "'policy_blocked', 'provider_refused', 'error', 'cancelled', 'waiting_timeout'"
)
NOTIFY = "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal'"


def _stop_reason(reasons: str) -> str:
    return (
        "(state = 'done') = (stop_reason IS NOT NULL) AND "
        f"(stop_reason IS NULL OR stop_reason IN ({reasons}))"
    )


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def _waited(table: str) -> list[Any]:
    """The columns and keys an approval and a question share."""
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("step", sa.Integer(), nullable=False),
        sa.Column("call_id", sa.String(length=200), nullable=False),
        sa.Column("addressed_to", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f(f"fk_{table}_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["run.id"], name=op.f(f"fk_{table}_run_id_run"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["addressed_to"], ["app_user.id"], name=op.f(f"fk_{table}_addressed_to_app_user")
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["message.id"],
            name=op.f(f"fk_{table}_message_id_message"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
        sa.UniqueConstraint(
            "run_id", "step", "call_id", name=op.f(f"uq_{table}_run_id_step_call_id")
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "approval",
        *_waited("approval"),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("args", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("subjects", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("summary", sa.String(length=500), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["decided_by"], ["app_user.id"], name=op.f("fk_approval_decided_by_app_user")
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'rejected', 'expired')",
            name=op.f("ck_approval_state"),
        ),
        sa.CheckConstraint(
            "(state IN ('approved', 'rejected')) = (decided_at IS NOT NULL)"
            " AND (decided_at IS NULL) = (decided_by IS NULL)",
            name=op.f("ck_approval_decided"),
        ),
        sa.CheckConstraint("char_length(reason) <= 500", name=op.f("ck_approval_reason_length")),
        sa.CheckConstraint("char_length(summary) <= 500", name=op.f("ck_approval_summary_length")),
    )
    op.create_index(op.f("ix_approval_org_id"), "approval", ["org_id"], unique=False)
    op.create_index("ix_approval_addressed_to_id", "approval", ["addressed_to", "id"])
    op.create_table(
        "run_question",
        *_waited("run_question"),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state IN ('pending', 'answered', 'expired')", name=op.f("ck_run_question_state")
        ),
        sa.CheckConstraint(
            "(state = 'answered') = (answer IS NOT NULL)"
            " AND (answer IS NULL) = (answered_at IS NULL)",
            name=op.f("ck_run_question_answered"),
        ),
        sa.CheckConstraint(
            "char_length(question) <= 1000", name=op.f("ck_run_question_question_length")
        ),
        sa.CheckConstraint(
            "char_length(answer) <= 4000", name=op.f("ck_run_question_answer_length")
        ),
    )
    op.create_index(op.f("ix_run_question_org_id"), "run_question", ["org_id"], unique=False)
    op.create_index("ix_run_question_addressed_to_id", "run_question", ["addressed_to", "id"])
    _replace_check(
        "message", "kind", "kind IN ('human', 'system', 'agent', 'approval', 'question')"
    )
    _replace_check("message", "author", AUTHOR.format(agent=f"kind IN {AGENT_KINDS}"))
    _replace_check("message", "agent_run", f"kind NOT IN {AGENT_KINDS} OR client_id IS NOT NULL")
    op.execute(sa.text(MESSAGE_PLACE.format(kinds=AGENT_KINDS)))
    _replace_check("notification", "reason", f"reason IN ({NOTIFY}, 'approval', 'question')")
    _replace_check("run", "stop_reason", _stop_reason(REASONS + ", 'approval_expired'"))


def downgrade() -> None:
    op.execute("UPDATE run SET stop_reason = 'error' WHERE stop_reason = 'approval_expired'")
    _replace_check("run", "stop_reason", _stop_reason(REASONS))
    op.execute("DELETE FROM notification WHERE reason IN ('approval', 'question')")
    _replace_check("notification", "reason", f"reason IN ({NOTIFY})")
    op.execute("DELETE FROM message WHERE kind IN ('approval', 'question')")
    op.execute(sa.text(MESSAGE_PLACE.format(kinds="('agent')")))
    _replace_check("message", "agent_run", "kind <> 'agent' OR client_id IS NOT NULL")
    _replace_check("message", "author", AUTHOR.format(agent="kind = 'agent'"))
    _replace_check("message", "kind", "kind IN ('human', 'system', 'agent')")
    op.drop_index("ix_run_question_addressed_to_id", table_name="run_question")
    op.drop_index(op.f("ix_run_question_org_id"), table_name="run_question")
    op.drop_table("run_question")
    op.drop_index("ix_approval_addressed_to_id", table_name="approval")
    op.drop_index(op.f("ix_approval_org_id"), table_name="approval")
    op.drop_table("approval")

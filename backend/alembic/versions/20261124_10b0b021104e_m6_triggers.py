"""m6 triggers (plan M6 task 8): runs that start from a mention or a ticket
assignment. `run.work_item_id` (the ticket a run was given as its task),
`run.chain_depth` (how many handovers from agent to agent led to it, at most 3), and
`run.trigger_message_id` may be empty (a run from an assignment has no message that
asked it; one of the two is always set). A run's stop notice may be a reply in a
channel's thread (the answer to a mention there): the message trigger function takes
system messages in any thread. Notification reason `run_stopped` (a run on a ticket
ended without an answer, or could not start: for the agent's responsible person).

Expand only: new nullable or defaulted columns, NOT NULL dropped, CHECKs widened, a
wider trigger. The previous release meets a run without a trigger message only once
this release wrote one (rolling update note, docs).

Revision ID: 10b0b021104e
Revises: e860d4fcc724
Create Date: 2026-11-14 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "10b0b021104e"
down_revision: str | None = "e860d4fcc724"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MESSAGE_PLACE = """
CREATE OR REPLACE FUNCTION herd_message_system_only_in_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'system' AND {replies} NOT EXISTS (
        SELECT 1 FROM conversation
        WHERE id = NEW.conversation_id AND kind IN ('thread_page', 'thread_ticket')
    ) AND NOT EXISTS (
        SELECT 1 FROM conversation_participant
        WHERE conversation_id = NEW.conversation_id AND principal_type = 'agent'
    ) THEN
        RAISE EXCEPTION 'system_message_outside_thread' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.kind IN ('agent', 'approval', 'question') AND NOT EXISTS (
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

NOTIFY = "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal', 'approval', 'question'"


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column("run", sa.Column("work_item_id", sa.UUID(), nullable=True))
    op.add_column(
        "run", sa.Column("chain_depth", sa.Integer(), server_default=sa.text("0"), nullable=False)
    )
    op.create_foreign_key(
        op.f("fk_run_work_item_id_work_item"),
        "run",
        "work_item",
        ["work_item_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_run_work_item_id", "run", ["work_item_id"], unique=False)
    op.alter_column("run", "trigger_message_id", existing_type=sa.UUID(), nullable=True)
    op.create_check_constraint(
        op.f("ck_run_trigger"), "run", "trigger_message_id IS NOT NULL OR work_item_id IS NOT NULL"
    )
    op.create_check_constraint(op.f("ck_run_chain_depth"), "run", "chain_depth BETWEEN 0 AND 3")
    op.execute(sa.text(MESSAGE_PLACE.format(replies="NEW.parent_id IS NULL AND")))
    _replace_check("notification", "reason", f"reason IN ({NOTIFY}, 'run_stopped')")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE reason = 'run_stopped'")
    _replace_check("notification", "reason", f"reason IN ({NOTIFY})")
    op.execute("DELETE FROM message WHERE kind = 'system' AND parent_id IS NOT NULL")
    op.execute(sa.text(MESSAGE_PLACE.format(replies="")))
    op.execute("DELETE FROM run WHERE trigger_message_id IS NULL")
    op.drop_constraint(op.f("ck_run_chain_depth"), "run", type_="check")
    op.drop_constraint(op.f("ck_run_trigger"), "run", type_="check")
    op.alter_column("run", "trigger_message_id", existing_type=sa.UUID(), nullable=False)
    op.drop_index("ix_run_work_item_id", table_name="run")
    op.drop_constraint(op.f("fk_run_work_item_id_work_item"), "run", type_="foreignkey")
    op.drop_column("run", "chain_depth")
    op.drop_column("run", "work_item_id")

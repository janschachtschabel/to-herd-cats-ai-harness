"""m6 writing tools (plan M6 task 6): agents as ticket assignees and reporters,
agents' messages in the conversations of their spaces (channels, page and ticket
threads) and the run that wrote a message (`message.run_id`), and notifications
about a proposal that has no thread to point at (a new page at the top level:
`notification.proposal_id` and `space_id`, no conversation and no message).

The message trigger function is replaced: an `agent` message is taken in a DM the
author agent takes part in (as before) and now also in a channel, page thread or
ticket thread of a space the author agent is a member of.

Expand only: CHECKs widened, nullable columns, NOT NULL dropped, a wider trigger.
The previous release never writes the new values; it reads `work_item` assignees of
type `agent` and notifications without a message only once this release wrote them
(rolling update note, docs).

Revision ID: 17c1453c21e1
Revises: d4f6a8c0e2b4
Create Date: 2026-11-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "17c1453c21e1"
down_revision: str | None = "d4f6a8c0e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

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

PREVIOUS_MESSAGE_PLACE = """
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

ASSIGNEE = "(assignee_type IS NULL) = (assignee_id IS NULL) AND (assignee_type IS NULL OR {})"
TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND space_id IS NULL) OR (message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NOT NULL AND space_id IS NOT NULL)"
)


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    _replace_check("work_item", "assignee", ASSIGNEE.format("assignee_type IN ('user', 'agent')"))
    _replace_check("work_item", "reporter_type", "reporter_type IN ('user', 'agent')")
    op.add_column("message", sa.Column("run_id", sa.UUID(), nullable=True))
    op.execute(sa.text(MESSAGE_PLACE))
    op.alter_column("notification", "conversation_id", nullable=True)
    op.alter_column("notification", "message_id", nullable=True)
    op.add_column("notification", sa.Column("proposal_id", sa.UUID(), nullable=True))
    op.add_column("notification", sa.Column("space_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notification_proposal_id_page_proposal"),
        "notification",
        "page_proposal",
        ["proposal_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        op.f("fk_notification_space_id_space"),
        "notification",
        "space",
        ["space_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(op.f("ck_notification_target"), "notification", TARGET)
    op.create_index(
        "uq_notification_proposal",
        "notification",
        ["user_id", "proposal_id", "reason"],
        unique=True,
        postgresql_where=sa.text("message_id IS NULL"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE message_id IS NULL")
    op.drop_index(
        "uq_notification_proposal",
        table_name="notification",
        postgresql_where=sa.text("message_id IS NULL"),
    )
    op.drop_constraint(op.f("ck_notification_target"), "notification", type_="check")
    op.drop_constraint(op.f("fk_notification_space_id_space"), "notification", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_notification_proposal_id_page_proposal"), "notification", type_="foreignkey"
    )
    op.drop_column("notification", "space_id")
    op.drop_column("notification", "proposal_id")
    op.alter_column("notification", "message_id", nullable=False)
    op.alter_column("notification", "conversation_id", nullable=False)
    op.execute(sa.text(PREVIOUS_MESSAGE_PLACE))
    op.execute(
        "DELETE FROM message WHERE kind = 'agent' AND conversation_id NOT IN"
        " (SELECT conversation_id FROM conversation_participant"
        " WHERE principal_type = 'agent')"
    )
    op.drop_column("message", "run_id")
    op.execute(
        "UPDATE work_item SET assignee_type = NULL, assignee_id = NULL"
        " WHERE assignee_type = 'agent'"
    )
    op.execute("DELETE FROM work_item WHERE reporter_type = 'agent'")
    _replace_check("work_item", "reporter_type", "reporter_type IN ('user')")
    _replace_check("work_item", "assignee", ASSIGNEE.format("assignee_type IN ('user')"))

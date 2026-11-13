"""m4 ticket threads: one conversation per ticket (kind `thread_ticket`,
`work_item_id`, removed with its ticket), system messages in ticket threads too, and
the notification reasons `assignment` and `ticket_comment`.

The trigger function of m3 messages is replaced so a `system` message is taken in a
page thread or a ticket thread and nowhere else (plan M4 Global Constraints).

Backward compatible: a nullable column, wider checks and a wider trigger that rows of
the previous release all meet; the previous release sees no ticket threads (its
visibility rule knows no such kind), so neither their messages nor their
notifications.

Revision ID: c5e7a9b1d3f5
Revises: b4d6f8a0c2e4
Create Date: 2026-11-15 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

SYSTEM_ONLY_IN_THREADS = """
CREATE OR REPLACE FUNCTION herd_message_system_only_in_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'system' AND NOT EXISTS (
        SELECT 1 FROM conversation
        WHERE id = NEW.conversation_id AND kind IN ({kinds})
    ) THEN
        RAISE EXCEPTION 'system_message_outside_thread' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

revision: str = "c5e7a9b1d3f5"
down_revision: str | None = "b4d6f8a0c2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("work_item_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_conversation_work_item_id_work_item"),
        "conversation",
        "work_item",
        ["work_item_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(
        op.f("uq_conversation_work_item_id"), "conversation", ["work_item_id"]
    )
    op.drop_constraint(op.f("ck_conversation_kind"), "conversation", type_="check")
    op.create_check_constraint(
        op.f("ck_conversation_kind"),
        "conversation",
        "kind IN ('channel', 'dm', 'thread_page', 'thread_ticket')",
    )
    op.create_check_constraint(
        op.f("ck_conversation_ticket_thread_fields"),
        "conversation",
        "(kind = 'thread_ticket') = (work_item_id IS NOT NULL)"
        " AND (kind <> 'thread_ticket' OR (space_id IS NOT NULL AND name IS NULL"
        " AND topic IS NULL))",
    )
    op.execute(sa.text(SYSTEM_ONLY_IN_THREADS.format(kinds="'thread_page', 'thread_ticket'")))
    op.drop_constraint(op.f("ck_notification_reason"), "notification", type_="check")
    op.create_check_constraint(
        op.f("ck_notification_reason"),
        "notification",
        "reason IN ('mention', 'reply', 'assignment', 'ticket_comment')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE reason IN ('assignment', 'ticket_comment')")
    op.execute("DELETE FROM conversation WHERE kind = 'thread_ticket'")
    op.drop_constraint(op.f("ck_notification_reason"), "notification", type_="check")
    op.create_check_constraint(
        op.f("ck_notification_reason"), "notification", "reason IN ('mention', 'reply')"
    )
    op.execute(sa.text(SYSTEM_ONLY_IN_THREADS.format(kinds="'thread_page'")))
    op.drop_constraint(op.f("ck_conversation_ticket_thread_fields"), "conversation", type_="check")
    op.drop_constraint(op.f("ck_conversation_kind"), "conversation", type_="check")
    op.create_check_constraint(
        op.f("ck_conversation_kind"), "conversation", "kind IN ('channel', 'dm', 'thread_page')"
    )
    op.drop_constraint(op.f("uq_conversation_work_item_id"), "conversation", type_="unique")
    op.drop_constraint(
        op.f("fk_conversation_work_item_id_work_item"), "conversation", type_="foreignkey"
    )
    op.drop_column("conversation", "work_item_id")

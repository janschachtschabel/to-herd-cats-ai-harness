"""m3 page threads: one conversation per wiki page (kind `thread_page`, `page_id`,
removed with its page), and system messages that refer to their event by `client_id`
(unique among system messages, which makes the timeline handler idempotent).

Backward compatible: a nullable column, a wider kind check and new checks and indexes
that rows of the previous release (channels, DMs, human messages) all meet; the
previous release does not see page threads.

Revision ID: a8c0e2f4b6d8
Revises: f7b9d1e3a5c7
Create Date: 2026-11-13 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c0e2f4b6d8"
down_revision: str | None = "f7b9d1e3a5c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("page_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_conversation_page_id_page"),
        "conversation",
        "page",
        ["page_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_unique_constraint(op.f("uq_conversation_page_id"), "conversation", ["page_id"])
    op.drop_constraint(op.f("ck_conversation_kind"), "conversation", type_="check")
    op.create_check_constraint(
        op.f("ck_conversation_kind"), "conversation", "kind IN ('channel', 'dm', 'thread_page')"
    )
    op.create_check_constraint(
        op.f("ck_conversation_thread_fields"),
        "conversation",
        "(kind = 'thread_page') = (page_id IS NOT NULL)"
        " AND (kind <> 'thread_page' OR (space_id IS NOT NULL AND name IS NULL"
        " AND topic IS NULL))",
    )
    op.create_check_constraint(
        op.f("ck_message_system_event"),
        "message",
        "author_type <> 'system' OR client_id IS NOT NULL",
    )
    op.create_index(
        "uq_message_system_client_id",
        "message",
        ["client_id"],
        unique=True,
        postgresql_where=sa.text("author_type = 'system'"),
    )


def downgrade() -> None:
    op.execute("DELETE FROM conversation WHERE kind = 'thread_page'")
    op.drop_index("uq_message_system_client_id", table_name="message")
    op.drop_constraint(op.f("ck_message_system_event"), "message", type_="check")
    op.drop_constraint(op.f("ck_conversation_thread_fields"), "conversation", type_="check")
    op.drop_constraint(op.f("ck_conversation_kind"), "conversation", type_="check")
    op.create_check_constraint(
        op.f("ck_conversation_kind"), "conversation", "kind IN ('channel', 'dm')"
    )
    op.drop_constraint(op.f("uq_conversation_page_id"), "conversation", type_="unique")
    op.drop_constraint(op.f("fk_conversation_page_id_page"), "conversation", type_="foreignkey")
    op.drop_column("conversation", "page_id")

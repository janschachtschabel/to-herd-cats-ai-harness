"""m3 messages: messages and one-level threads, and the database's guarantee that a
`system` message exists only in a page thread (review focus 7).

Two triggers carry the guarantee, so no code path, not even one that bypasses the
services, can break it: a message of kind `system` is refused unless its
conversation is a `thread_page`, and a conversation's kind never changes (so a
thread's system messages cannot end up in a channel or a direct message).

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-11-13 15:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

SYSTEM_ONLY_IN_THREADS = """
CREATE FUNCTION herd_message_system_only_in_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'system' AND NOT EXISTS (
        SELECT 1 FROM conversation WHERE id = NEW.conversation_id AND kind = 'thread_page'
    ) THEN
        RAISE EXCEPTION 'system_message_outside_thread' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

KIND_FIXED = """
CREATE FUNCTION herd_conversation_kind_fixed() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind IS DISTINCT FROM OLD.kind THEN
        RAISE EXCEPTION 'conversation_kind_fixed' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

revision: str = "c3e5a7b9d1f3"
down_revision: str | None = "b2d4f6a8c0e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "message",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("body_md", sa.Text(), nullable=False),
        sa.Column("client_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reply_count", sa.Integer(), nullable=False),
        sa.Column("last_reply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(kind = 'system') = (author_type = 'system') AND (author_type = 'system') = (author_id IS NULL)",
            name=op.f("ck_message_author"),
        ),
        sa.CheckConstraint(
            "author_type IN ('user', 'system')", name=op.f("ck_message_author_type")
        ),
        sa.CheckConstraint("kind IN ('human', 'system')", name=op.f("ck_message_kind")),
        sa.CheckConstraint("char_length(body_md) <= 20000", name=op.f("ck_message_body_length")),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_message_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_message_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["message.id"],
            name=op.f("fk_message_parent_id_message"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message")),
        sa.UniqueConstraint("author_id", "client_id", name=op.f("uq_message_author_id_client_id")),
    )
    op.create_index(
        "ix_message_conversation_id_top",
        "message",
        ["conversation_id", "id"],
        unique=False,
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.create_index(op.f("ix_message_org_id"), "message", ["org_id"], unique=False)
    op.create_index("ix_message_parent_id", "message", ["parent_id", "id"], unique=False)
    op.execute(sa.text(SYSTEM_ONLY_IN_THREADS))
    op.execute(
        sa.text(
            "CREATE TRIGGER message_system_only_in_threads"
            " BEFORE INSERT OR UPDATE OF kind, conversation_id ON message"
            " FOR EACH ROW EXECUTE FUNCTION herd_message_system_only_in_threads()"
        )
    )
    op.execute(sa.text(KIND_FIXED))
    op.execute(
        sa.text(
            "CREATE TRIGGER conversation_kind_fixed BEFORE UPDATE OF kind ON conversation"
            " FOR EACH ROW EXECUTE FUNCTION herd_conversation_kind_fixed()"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER conversation_kind_fixed ON conversation"))
    op.execute(sa.text("DROP FUNCTION herd_conversation_kind_fixed()"))
    op.execute(sa.text("DROP TRIGGER message_system_only_in_threads ON message"))
    op.execute(sa.text("DROP FUNCTION herd_message_system_only_in_threads()"))
    op.drop_index("ix_message_parent_id", table_name="message")
    op.drop_index(op.f("ix_message_org_id"), table_name="message")
    op.drop_index(
        "ix_message_conversation_id_top",
        table_name="message",
        postgresql_where=sa.text("parent_id IS NULL"),
    )
    op.drop_table("message")

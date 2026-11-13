"""m3 one-level threads: the database refuses what `threads.lock_parent` refuses
(review M3 N15), so no writer that bypasses the services (M6 adds agents) can make a
deeper thread.

A trigger on `message` (insert, or an update of `parent_id` or `conversation_id`):
- a reply's parent must be a top-level message of the same conversation;
- a message with replies can neither become a reply nor move to another conversation.

Backward compatible: the previous release (M2) has no messages; M3's services never
write such rows.

Revision ID: e3a5c7d9f1b3
Revises: d2f4b6c8e0a2
Create Date: 2026-11-14 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

ONE_LEVEL = """
CREATE FUNCTION herd_message_one_level_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.parent_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM message
        WHERE id = NEW.parent_id
          AND conversation_id = NEW.conversation_id
          AND parent_id IS NULL
    ) THEN
        RAISE EXCEPTION 'reply_not_one_level' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE'
       AND (NEW.parent_id IS NOT NULL OR NEW.conversation_id <> OLD.conversation_id)
       AND EXISTS (SELECT 1 FROM message WHERE parent_id = NEW.id)
    THEN
        RAISE EXCEPTION 'reply_not_one_level' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

revision: str = "e3a5c7d9f1b3"
down_revision: str | None = "d2f4b6c8e0a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(sa.text(ONE_LEVEL))
    op.execute(
        sa.text(
            "CREATE TRIGGER message_one_level_threads"
            " BEFORE INSERT OR UPDATE OF parent_id, conversation_id ON message"
            " FOR EACH ROW EXECUTE FUNCTION herd_message_one_level_threads()"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER message_one_level_threads ON message"))
    op.execute(sa.text("DROP FUNCTION herd_message_one_level_threads()"))

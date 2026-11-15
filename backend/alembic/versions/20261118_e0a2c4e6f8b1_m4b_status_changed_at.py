"""m4b status changed at: when a ticket's status last changed (`work_item.status_changed_at`),
for the daily view ("changed since the last working day") and my board ("done in the
last 14 days"), plan M4b decisions 4 and 5.

- A new ticket has the time it was inserted (default `now()`); a change of `status_id`
  sets it again (trigger `work_item_status_changed_at`), whatever code writes: the
  previous release's too, and a status deleted with a replacement.
- Existing tickets get the time of the last status entry in their timeline (`ticket.
  status_changed` or `ticket.created`), or their creation time where there is none.

Backward compatible: a column with a default and a trigger that only sets it; the
previous release neither reads nor writes it.

Revision ID: e0a2c4e6f8b1
Revises: d8f0b2c4e6a8
Create Date: 2026-11-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e0a2c4e6f8b1"
down_revision: str | None = "d8f0b2c4e6a8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BACKFILL = """
UPDATE work_item w SET status_changed_at = COALESCE(
    (
        SELECT max(m.created_at)
        FROM message m JOIN conversation c ON c.id = m.conversation_id
        WHERE c.work_item_id = w.id AND m.kind = 'system'
          AND (m.body_md LIKE '%"ticket.status_changed"%'
               OR m.body_md LIKE '%"ticket.created"%')
    ),
    w.created_at
)
"""

STATUS_CHANGED_AT = """
CREATE FUNCTION herd_work_item_status_changed_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.status_id IS DISTINCT FROM OLD.status_id THEN
        NEW.status_changed_at := now();
    END IF;
    RETURN NEW;
END
$$
"""


def upgrade() -> None:
    op.add_column(
        "work_item",
        sa.Column(
            "status_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.execute(sa.text(BACKFILL))
    op.execute(sa.text(STATUS_CHANGED_AT))
    op.execute(
        sa.text(
            "CREATE TRIGGER work_item_status_changed_at"
            " BEFORE UPDATE OF status_id ON work_item"
            " FOR EACH ROW EXECUTE FUNCTION herd_work_item_status_changed_at()"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER work_item_status_changed_at ON work_item"))
    op.execute(sa.text("DROP FUNCTION herd_work_item_status_changed_at()"))
    op.drop_column("work_item", "status_changed_at")

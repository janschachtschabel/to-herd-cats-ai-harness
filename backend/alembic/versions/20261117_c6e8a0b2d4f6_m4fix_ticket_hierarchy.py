"""m4fix ticket hierarchy: the parent rule in the database (review M4 P7), whatever code
writes a ticket: no ticket is its own parent; a parent is in the same organisation and
space and of a kind that may sit above the child (epic above story, task and bug;
story above task and bug); a ticket whose children would no longer fit does not
change its kind or its space. The kinds are strictly ordered, so a cycle cannot
happen. The parent is read `FOR SHARE`, as the service holds it, so a kind change of
the parent and a new child under it run one after the other.

Backward compatible: a trigger that refuses only what the previous release's service
refuses already (`tickets/hierarchy.py`).

Revision ID: c6e8a0b2d4f6
Revises: b5d7f9a1c3e5
Create Date: 2026-11-17 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c6e8a0b2d4f6"
down_revision: str | None = "b5d7f9a1c3e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (parent kind, child kind) pairs the hierarchy allows (plan M4 decision 5).
ALLOWED = "('epic','story'),('epic','task'),('epic','bug'),('story','task'),('story','bug')"

HIERARCHY = f"""
CREATE FUNCTION herd_work_item_hierarchy() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    parent_kind text;
BEGIN
    IF NEW.parent_id IS NOT NULL THEN
        IF NEW.parent_id = NEW.id THEN
            RAISE EXCEPTION 'work_item_parent_self' USING ERRCODE = 'check_violation';
        END IF;
        SELECT kind INTO parent_kind FROM work_item
        WHERE id = NEW.parent_id AND org_id = NEW.org_id AND space_id = NEW.space_id
        FOR SHARE;
        IF parent_kind IS NULL THEN
            RAISE EXCEPTION 'work_item_parent_other_space' USING ERRCODE = 'check_violation';
        END IF;
        IF (parent_kind, NEW.kind::text) NOT IN ({ALLOWED}) THEN
            RAISE EXCEPTION 'work_item_parent_kind' USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND (
        NEW.kind IS DISTINCT FROM OLD.kind
        OR NEW.space_id IS DISTINCT FROM OLD.space_id
        OR NEW.org_id IS DISTINCT FROM OLD.org_id
    ) AND EXISTS (
        SELECT 1 FROM work_item c
        WHERE c.parent_id = NEW.id
          AND (c.space_id <> NEW.space_id OR c.org_id <> NEW.org_id
               OR (NEW.kind::text, c.kind::text) NOT IN ({ALLOWED}))
    ) THEN
        RAISE EXCEPTION 'work_item_children_do_not_fit' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""  # noqa: S608 -- constants only


def upgrade() -> None:
    op.execute(sa.text(HIERARCHY))
    op.execute(
        sa.text(
            "CREATE TRIGGER work_item_hierarchy"
            " BEFORE INSERT OR UPDATE OF parent_id, kind, space_id, org_id ON work_item"
            " FOR EACH ROW EXECUTE FUNCTION herd_work_item_hierarchy()"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER work_item_hierarchy ON work_item"))
    op.execute(sa.text("DROP FUNCTION herd_work_item_hierarchy()"))

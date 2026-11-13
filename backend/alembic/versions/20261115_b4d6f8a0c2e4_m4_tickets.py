"""m4 tickets: statuses per space, the ticket counter per organisation, and tickets
(`work_item`).

- Every space gets five statuses when it is inserted (trigger
  `space_default_ticket_statuses`), whatever code inserts it: the previous release
  creates spaces too while this one rolls out. Spaces that exist get them here. The
  names are German (the default language; organisations have no language of their
  own), written once, and data from then on.
- A ticket's parent and its status are in the ticket's space (trigger
  `work_item_same_space`), whatever code writes it.

Backward compatible: new tables and a trigger that only adds rows; the previous
release reads none of them.

Revision ID: b4d6f8a0c2e4
Revises: e3a5c7d9f1b3
Create Date: 2026-11-13 17:17:19.497991
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

DEFAULT_STATUSES = """
    (0, 'Neu', 'open'),
    (1, 'In Arbeit', 'active'),
    (2, 'Zur Prüfung', 'review'),
    (3, 'Erledigt', 'done'),
    (4, 'Verworfen', 'cancelled')
"""

# The default statuses of every space that has none (the trigger: of the new one).
BACKFILL = f"""
INSERT INTO ticket_status (id, org_id, space_id, name, position, category, version)
SELECT gen_random_uuid(), s.org_id, s.id, d.name, d.position, d.category, 1
FROM space s CROSS JOIN (VALUES {DEFAULT_STATUSES}) AS d(position, name, category)
WHERE NOT EXISTS (SELECT 1 FROM ticket_status t WHERE t.space_id = s.id)
"""  # noqa: S608 -- constants only

DEFAULTS_FOR_NEW_SPACE = f"""
CREATE FUNCTION herd_space_default_ticket_statuses() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO ticket_status (id, org_id, space_id, name, position, category, version)
    SELECT gen_random_uuid(), NEW.org_id, NEW.id, d.name, d.position, d.category, 1
    FROM (VALUES {DEFAULT_STATUSES}) AS d(position, name, category);
    RETURN NULL;
END
$$
"""  # noqa: S608 -- constants only

SAME_SPACE = """
CREATE FUNCTION herd_work_item_same_space() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.parent_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM work_item WHERE id = NEW.parent_id AND space_id = NEW.space_id
    ) THEN
        RAISE EXCEPTION 'work_item_parent_other_space' USING ERRCODE = 'check_violation';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM ticket_status WHERE id = NEW.status_id AND space_id = NEW.space_id
    ) THEN
        RAISE EXCEPTION 'work_item_status_other_space' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""

revision: str = "b4d6f8a0c2e4"
down_revision: str | None = "e3a5c7d9f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_counter",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_ticket_counter_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("org_id", name=op.f("pk_ticket_counter")),
    )
    op.create_table(
        "ticket_status",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "category IN ('open', 'active', 'review', 'done', 'cancelled')",
            name=op.f("ck_ticket_status_category"),
        ),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 40", name=op.f("ck_ticket_status_name_length")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_ticket_status_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_ticket_status_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ticket_status")),
    )
    op.create_index(op.f("ix_ticket_status_org_id"), "ticket_status", ["org_id"], unique=False)
    op.create_index(
        "ix_ticket_status_space_id_position",
        "ticket_status",
        ["space_id", "position"],
        unique=False,
    )
    op.create_index(
        "uq_ticket_status_space_id_name",
        "ticket_status",
        ["space_id", sa.literal_column("lower(name)").label("name_lower")],
        unique=True,
    )
    op.create_table(
        "work_item",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description_md", sa.Text(), nullable=False),
        sa.Column("status_id", sa.UUID(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("assignee_type", sa.String(length=16), nullable=True),
        sa.Column("assignee_id", sa.UUID(), nullable=True),
        sa.Column("reporter_type", sa.String(length=16), nullable=False),
        sa.Column("reporter_id", sa.UUID(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('german'::regconfig, title), 'A') || setweight(to_tsvector('simple'::regconfig, title), 'A') || setweight(to_tsvector('german'::regconfig, description_md), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(assignee_type IS NULL) = (assignee_id IS NULL) AND (assignee_type IS NULL OR assignee_type IN ('user'))",
            name=op.f("ck_work_item_assignee"),
        ),
        sa.CheckConstraint(
            "kind IN ('epic', 'story', 'task', 'bug')", name=op.f("ck_work_item_kind")
        ),
        sa.CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')", name=op.f("ck_work_item_priority")
        ),
        sa.CheckConstraint("reporter_type IN ('user')", name=op.f("ck_work_item_reporter_type")),
        sa.CheckConstraint(
            "char_length(description_md) <= 100000", name=op.f("ck_work_item_description_length")
        ),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name=op.f("ck_work_item_title_length")
        ),
        sa.CheckConstraint("parent_id <> id", name=op.f("ck_work_item_parent_not_self")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_work_item_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["work_item.id"],
            name=op.f("fk_work_item_parent_id_work_item"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["space.id"], name=op.f("fk_work_item_space_id_space"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["status_id"], ["ticket_status.id"], name=op.f("fk_work_item_status_id_ticket_status")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_work_item")),
        sa.UniqueConstraint("org_id", "number", name=op.f("uq_work_item_org_id_number")),
    )
    op.create_index(
        "ix_work_item_assignee", "work_item", ["assignee_type", "assignee_id"], unique=False
    )
    op.create_index(op.f("ix_work_item_org_id"), "work_item", ["org_id"], unique=False)
    op.create_index("ix_work_item_parent_id", "work_item", ["parent_id"], unique=False)
    op.create_index(
        "ix_work_item_search_tsv", "work_item", ["search_tsv"], unique=False, postgresql_using="gin"
    )
    op.create_index(
        "ix_work_item_space_id_status_id", "work_item", ["space_id", "status_id"], unique=False
    )
    op.execute(sa.text(DEFAULTS_FOR_NEW_SPACE))
    op.execute(
        sa.text(
            "CREATE TRIGGER space_default_ticket_statuses AFTER INSERT ON space"
            " FOR EACH ROW EXECUTE FUNCTION herd_space_default_ticket_statuses()"
        )
    )
    op.execute(sa.text(BACKFILL))
    op.execute(sa.text(SAME_SPACE))
    op.execute(
        sa.text(
            "CREATE TRIGGER work_item_same_space"
            " BEFORE INSERT OR UPDATE OF parent_id, status_id, space_id ON work_item"
            " FOR EACH ROW EXECUTE FUNCTION herd_work_item_same_space()"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DROP TRIGGER work_item_same_space ON work_item"))
    op.execute(sa.text("DROP FUNCTION herd_work_item_same_space()"))
    op.execute(sa.text("DROP TRIGGER space_default_ticket_statuses ON space"))
    op.execute(sa.text("DROP FUNCTION herd_space_default_ticket_statuses()"))
    op.drop_index("ix_work_item_space_id_status_id", table_name="work_item")
    op.drop_index("ix_work_item_search_tsv", table_name="work_item", postgresql_using="gin")
    op.drop_index("ix_work_item_parent_id", table_name="work_item")
    op.drop_index(op.f("ix_work_item_org_id"), table_name="work_item")
    op.drop_index("ix_work_item_assignee", table_name="work_item")
    op.drop_table("work_item")
    op.drop_index("uq_ticket_status_space_id_name", table_name="ticket_status")
    op.drop_index("ix_ticket_status_space_id_position", table_name="ticket_status")
    op.drop_index(op.f("ix_ticket_status_org_id"), table_name="ticket_status")
    op.drop_table("ticket_status")
    op.drop_table("ticket_counter")

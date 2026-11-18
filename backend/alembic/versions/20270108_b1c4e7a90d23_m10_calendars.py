"""m10 calendars (plan M10 task 1, decision 2): calendars per space (`calendar`, at
most one default per space by a partial unique index; a default has no name until
renamed; `(id, space_id)` unique for the events' foreign key) and the organisation's calendar switches (`calendar_setting`, the
sync switch behind the derived right `calendar.sync`; no row means off).

Expand only: two new tables. The previous release (1.0.0) neither reads nor writes
them.

Revision ID: b1c4e7a90d23
Revises: daa60bc7c565
Create Date: 2027-01-08 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c4e7a90d23"
down_revision: str | None = "daa60bc7c565"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "calendar_setting",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("sync_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_calendar_setting_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("org_id", name=op.f("pk_calendar_setting")),
    )
    op.create_table(
        "calendar",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("color", sa.String(length=16), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "color IN ('blue', 'green', 'amber', 'red', 'violet', 'teal', 'pink', 'slate')",
            name=op.f("ck_calendar_color"),
        ),
        sa.CheckConstraint("name IS NOT NULL OR is_default", name=op.f("ck_calendar_name")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_calendar_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["space.id"], name=op.f("fk_calendar_space_id_space"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar")),
        sa.UniqueConstraint("id", "space_id", name=op.f("uq_calendar_id_space_id")),
    )
    op.create_index(op.f("ix_calendar_org_id"), "calendar", ["org_id"], unique=False)
    op.create_index("ix_calendar_space_id", "calendar", ["space_id"], unique=False)
    op.create_index(
        "uq_calendar_space_id_default",
        "calendar",
        ["space_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_calendar_space_id_default",
        table_name="calendar",
        postgresql_where=sa.text("is_default"),
    )
    op.drop_index("ix_calendar_space_id", table_name="calendar")
    op.drop_index(op.f("ix_calendar_org_id"), table_name="calendar")
    op.drop_table("calendar")
    op.drop_table("calendar_setting")

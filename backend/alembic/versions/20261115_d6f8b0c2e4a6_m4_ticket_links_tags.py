"""m4 ticket links and tags: the pages a ticket links (`ticket_page_link`, gone with
either end) and tickets as subjects of tags (`tagging.subject_type` widened).

Backward compatible: a new table and a wider check that rows of the previous release
all meet; the previous release neither reads the table nor writes ticket taggings.

Revision ID: d6f8b0c2e4a6
Revises: c5e7a9b1d3f5
Create Date: 2026-11-15 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6f8b0c2e4a6"
down_revision: str | None = "c5e7a9b1d3f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_page_link",
        sa.Column("work_item_id", sa.UUID(), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_ticket_page_link_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_ticket_page_link_page_id_page"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["work_item_id"],
            ["work_item.id"],
            name=op.f("fk_ticket_page_link_work_item_id_work_item"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("work_item_id", "page_id", name=op.f("pk_ticket_page_link")),
    )
    op.create_index(
        op.f("ix_ticket_page_link_org_id"), "ticket_page_link", ["org_id"], unique=False
    )
    op.create_index("ix_ticket_page_link_page_id", "ticket_page_link", ["page_id"], unique=False)
    op.drop_constraint(op.f("ck_tagging_subject_type"), "tagging", type_="check")
    op.create_check_constraint(
        op.f("ck_tagging_subject_type"), "tagging", "subject_type IN ('page', 'ticket')"
    )


def downgrade() -> None:
    op.execute("DELETE FROM tagging WHERE subject_type = 'ticket'")
    op.drop_constraint(op.f("ck_tagging_subject_type"), "tagging", type_="check")
    op.create_check_constraint(
        op.f("ck_tagging_subject_type"), "tagging", "subject_type IN ('page')"
    )
    op.drop_index("ix_ticket_page_link_page_id", table_name="ticket_page_link")
    op.drop_index(op.f("ix_ticket_page_link_org_id"), table_name="ticket_page_link")
    op.drop_table("ticket_page_link")

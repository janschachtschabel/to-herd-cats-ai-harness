"""m2 pages: wiki pages with materialised paths, unique per space outside the trash.

Revision ID: 5c1e2a9d7b40
Revises: 78d0e3996d2d
Create Date: 2026-11-13 01:41:58.327800
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5c1e2a9d7b40"
down_revision: str | None = "78d0e3996d2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("collab_generation", sa.Integer(), nullable=False),
        sa.Column("trashed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_type", sa.String(length=16), nullable=False),
        sa.Column("created_by_id", sa.UUID(), nullable=False),
        sa.Column("updated_by_type", sa.String(length=16), nullable=False),
        sa.Column("updated_by_id", sa.UUID(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('draft', 'published')", name=op.f("ck_page_status")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_page_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["parent_id"], ["page.id"], name=op.f("fk_page_parent_id_page")),
        sa.ForeignKeyConstraint(
            ["space_id"], ["space.id"], name=op.f("fk_page_space_id_space"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page")),
    )
    op.create_index(op.f("ix_page_org_id"), "page", ["org_id"], unique=False)
    op.create_index("ix_page_space_id_parent_id", "page", ["space_id", "parent_id"], unique=False)
    op.create_index(
        "uq_page_space_id_path_live",
        "page",
        ["space_id", "path"],
        unique=True,
        postgresql_where=sa.text("trashed_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_page_space_id_path_live",
        table_name="page",
        postgresql_where=sa.text("trashed_at IS NULL"),
    )
    op.drop_index("ix_page_space_id_parent_id", table_name="page")
    op.drop_index(op.f("ix_page_org_id"), table_name="page")
    op.drop_table("page")

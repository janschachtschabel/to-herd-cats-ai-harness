"""m2 page versions: one row per saved state of a page, numbered per page.

Revision ID: 8f3b6d2c1a57
Revises: 5c1e2a9d7b40
Create Date: 2026-11-13 01:57:14.434884
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f3b6d2c1a57"
down_revision: str | None = "5c1e2a9d7b40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_version",
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("change_summary", sa.String(length=300), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("session_key", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "source IN ('human', 'import', 'restore', 'collab')",
            name=op.f("ck_page_version_source"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_page_version_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"], ["page.id"], name=op.f("fk_page_version_page_id_page"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_version")),
        sa.UniqueConstraint("page_id", "number", name=op.f("uq_page_version_page_id_number")),
    )
    op.create_index(op.f("ix_page_version_org_id"), "page_version", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_page_version_org_id"), table_name="page_version")
    op.drop_table("page_version")

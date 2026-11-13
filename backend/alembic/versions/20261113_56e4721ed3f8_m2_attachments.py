"""m2 attachments: files on pages, stored once per organisation and content.

Revision ID: 56e4721ed3f8
Revises: c11bf0d84e50
Create Date: 2026-11-13 02:39:52.091746
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "56e4721ed3f8"
down_revision: str | None = "c11bf0d84e50"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachment",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime", sa.String(length=100), nullable=False),
        sa.Column("size", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_key", sa.String(length=200), nullable=False),
        sa.Column("uploaded_by_type", sa.String(length=16), nullable=False),
        sa.Column("uploaded_by_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_attachment_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"], ["page.id"], name=op.f("fk_attachment_page_id_page"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_attachment_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attachment")),
    )
    op.create_index(op.f("ix_attachment_org_id"), "attachment", ["org_id"], unique=False)
    op.create_index("ix_attachment_org_id_sha256", "attachment", ["org_id", "sha256"], unique=False)
    op.create_index("ix_attachment_page_id", "attachment", ["page_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_attachment_page_id", table_name="attachment")
    op.drop_index("ix_attachment_org_id_sha256", table_name="attachment")
    op.drop_index(op.f("ix_attachment_org_id"), table_name="attachment")
    op.drop_table("attachment")

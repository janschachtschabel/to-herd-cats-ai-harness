"""m2 tags: one pool per organisation (system-wide or per space) and taggings.

Revision ID: 94ab8cb957eb
Revises: 8f3b6d2c1a57
Create Date: 2026-11-13 02:17:18.559390
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "94ab8cb957eb"
down_revision: str | None = "8f3b6d2c1a57"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tag",
        sa.Column("space_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("color ~ '^#[0-9a-f]{6}$'", name=op.f("ck_tag_color")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_tag_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["space.id"], name=op.f("fk_tag_space_id_space"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag")),
    )
    op.create_index(op.f("ix_tag_org_id"), "tag", ["org_id"], unique=False)
    op.create_index(
        "uq_tag_org_id_name_system",
        "tag",
        ["org_id", sa.literal_column("lower(name)")],
        unique=True,
        postgresql_where=sa.text("space_id IS NULL"),
    )
    op.create_index(
        "uq_tag_space_id_name",
        "tag",
        ["space_id", sa.literal_column("lower(name)")],
        unique=True,
        postgresql_where=sa.text("space_id IS NOT NULL"),
    )
    op.create_table(
        "tagging",
        sa.Column("tag_id", sa.UUID(), nullable=False),
        sa.Column("subject_type", sa.String(length=16), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("subject_type IN ('page')", name=op.f("ck_tagging_subject_type")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_tagging_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tag.id"], name=op.f("fk_tagging_tag_id_tag"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("tag_id", "subject_type", "subject_id", name=op.f("pk_tagging")),
    )
    op.create_index(op.f("ix_tagging_org_id"), "tagging", ["org_id"], unique=False)
    op.create_index("ix_tagging_subject", "tagging", ["subject_type", "subject_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_tagging_subject", table_name="tagging")
    op.drop_index(op.f("ix_tagging_org_id"), table_name="tagging")
    op.drop_table("tagging")
    op.drop_index(
        "uq_tag_space_id_name", table_name="tag", postgresql_where=sa.text("space_id IS NOT NULL")
    )
    op.drop_index(
        "uq_tag_org_id_name_system", table_name="tag", postgresql_where=sa.text("space_id IS NULL")
    )
    op.drop_index(op.f("ix_tag_org_id"), table_name="tag")
    op.drop_table("tag")

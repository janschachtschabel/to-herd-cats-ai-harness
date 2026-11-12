"""m1 groups: groups and their members (people only until agents arrive in M6).

Revision ID: 3394046add1d
Revises: ed6fa007a1fb
Create Date: 2026-11-12 21:23:33.044461
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "3394046add1d"
down_revision: str | None = "ed6fa007a1fb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_group",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_user_group_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_group")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_user_group_org_id_name")),
    )
    op.create_index(op.f("ix_user_group_org_id"), "user_group", ["org_id"], unique=False)
    op.create_table(
        "group_member",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("member_type", sa.String(length=16), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("member_type IN ('user')", name=op.f("ck_group_member_member_type")),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_group.id"],
            name=op.f("fk_group_member_group_id_user_group"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "group_id", "member_type", "member_id", name=op.f("pk_group_member")
        ),
    )
    op.create_index(
        "ix_group_member_principal", "group_member", ["member_type", "member_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_group_member_principal", table_name="group_member")
    op.drop_table("group_member")
    op.drop_index(op.f("ix_user_group_org_id"), table_name="user_group")
    op.drop_table("user_group")

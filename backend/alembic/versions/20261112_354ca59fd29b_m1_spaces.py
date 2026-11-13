"""m1 spaces: open, team and personal spaces and their members (people and groups).

Revision ID: 354ca59fd29b
Revises: 3394046add1d
Create Date: 2026-11-12 21:28:16.553114
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "354ca59fd29b"
down_revision: str | None = "3394046add1d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "space",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("icon", sa.String(length=32), nullable=True),
        sa.Column("owner_user_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(kind = 'personal') = (owner_user_id IS NOT NULL)",
            name=op.f("ck_space_personal_owner"),
        ),
        sa.CheckConstraint("kind IN ('open', 'team', 'personal')", name=op.f("ck_space_kind")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_space_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["app_user.id"], name=op.f("fk_space_owner_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_space")),
        sa.UniqueConstraint("org_id", "owner_user_id", name=op.f("uq_space_org_id_owner_user_id")),
    )
    op.create_index(op.f("ix_space_org_id"), "space", ["org_id"], unique=False)
    op.create_table(
        "space_member",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("member_type", sa.String(length=16), nullable=False),
        sa.Column("member_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.CheckConstraint(
            "member_type IN ('user', 'group')", name=op.f("ck_space_member_member_type")
        ),
        sa.CheckConstraint(
            "role IN ('viewer', 'editor', 'moderator', 'admin')", name=op.f("ck_space_member_role")
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_space_member_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "space_id", "member_type", "member_id", name=op.f("pk_space_member")
        ),
    )
    op.create_index(
        "ix_space_member_principal", "space_member", ["member_type", "member_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_space_member_principal", table_name="space_member")
    op.drop_table("space_member")
    op.drop_index(op.f("ix_space_org_id"), table_name="space")
    op.drop_table("space")

"""m5 ai assignments: the organisation's standard assignment, the ordered group
assignments and a person's own (spec 7.2); `ai.use` is derived from them.

Backward compatible: new tables the previous release does not know. Connections they
use cannot be deleted (RESTRICT); a group or person takes its row along (CASCADE).

Revision ID: f2b4d6f8a0c2
Revises: e1a3c5e7f9b1
Create Date: 2026-11-16 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2b4d6f8a0c2"
down_revision: str | None = "e1a3c5e7f9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _connection_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["connection_id"],
        ["ai_connection.id"],
        name=op.f(f"fk_{table}_connection_id_ai_connection"),
        ondelete="RESTRICT",
    )


def _org_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["org_id"],
        ["organization.id"],
        name=op.f(f"fk_{table}_org_id_organization"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "ai_org_assignment",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "(connection_id IS NULL) = (model IS NULL)", name=op.f("ck_ai_org_assignment_target")
        ),
        _connection_fk("ai_org_assignment"),
        _org_fk("ai_org_assignment"),
        sa.PrimaryKeyConstraint("org_id", name=op.f("pk_ai_org_assignment")),
    )
    op.create_index(
        op.f("ix_ai_org_assignment_connection_id"),
        "ai_org_assignment",
        ["connection_id"],
        unique=False,
    )
    op.create_table(
        "ai_group_assignment",
        sa.Column("group_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        _connection_fk("ai_group_assignment"),
        sa.ForeignKeyConstraint(
            ["group_id"],
            ["user_group.id"],
            name=op.f("fk_ai_group_assignment_group_id_user_group"),
            ondelete="CASCADE",
        ),
        _org_fk("ai_group_assignment"),
        sa.PrimaryKeyConstraint("group_id", name=op.f("pk_ai_group_assignment")),
        sa.UniqueConstraint(
            "org_id", "position", name=op.f("uq_ai_group_assignment_org_id_position")
        ),
    )
    op.create_index(
        op.f("ix_ai_group_assignment_connection_id"),
        "ai_group_assignment",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_group_assignment_org_id"), "ai_group_assignment", ["org_id"], unique=False
    )
    op.create_table(
        "ai_user_assignment",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("no_ai", sa.Boolean(), nullable=False),
        sa.Column("connection_id", sa.UUID(), nullable=True),
        sa.Column("model", sa.String(length=200), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(connection_id IS NULL) = (model IS NULL)", name=op.f("ck_ai_user_assignment_target")
        ),
        sa.CheckConstraint(
            "no_ai = (connection_id IS NULL)", name=op.f("ck_ai_user_assignment_no_ai")
        ),
        _connection_fk("ai_user_assignment"),
        _org_fk("ai_user_assignment"),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_ai_user_assignment_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_ai_user_assignment")),
    )
    op.create_index(
        op.f("ix_ai_user_assignment_connection_id"),
        "ai_user_assignment",
        ["connection_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_user_assignment_org_id"), "ai_user_assignment", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("ai_user_assignment")
    op.drop_table("ai_group_assignment")
    op.drop_table("ai_org_assignment")

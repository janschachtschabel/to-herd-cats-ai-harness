"""m1 audit: the append-only audit log, with at most one admin-access entry per
admin, space and UTC day.

Revision ID: 78d0e3996d2d
Revises: 354ca59fd29b
Create Date: 2026-11-12 21:43:54.348043
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "78d0e3996d2d"
down_revision: str | None = "354ca59fd29b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_audit_log_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(op.f("ix_audit_log_org_id"), "audit_log", ["org_id"], unique=False)
    op.create_index(
        "ix_audit_log_org_id_created_at", "audit_log", ["org_id", "created_at", "id"], unique=False
    )
    op.create_index(
        "uq_audit_log_admin_access_daily",
        "audit_log",
        ["actor_id", "target_id", sa.literal_column("((created_at AT TIME ZONE 'UTC')::date)")],
        unique=True,
        postgresql_where=sa.text("action = 'space.admin_access'"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_audit_log_admin_access_daily",
        table_name="audit_log",
        postgresql_where=sa.text("action = 'space.admin_access'"),
    )
    op.drop_index("ix_audit_log_org_id_created_at", table_name="audit_log")
    op.drop_index(op.f("ix_audit_log_org_id"), table_name="audit_log")
    op.drop_table("audit_log")

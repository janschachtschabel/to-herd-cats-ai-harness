"""m9 maintenance (plan M9 task 12, decision 9): `maintenance`, one row per
organisation: `active`, `reason` (`restore`), `started_at`, `version`. While a row is
active the API answers 503 and the worker's loops pause.

Expand only: one new table. The previous release neither reads nor writes it (and
knows no maintenance: replace a running installation only with this release or later).

Revision ID: a3c5e7f9b2d4
Revises: 9e4b6d2f8a17
Create Date: 2027-01-04 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3c5e7f9b2d4"
down_revision: str | None = "9e4b6d2f8a17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "maintenance",
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("reason IN ('restore')", name=op.f("ck_maintenance_reason")),
        sa.CheckConstraint(
            "(active AND reason IS NOT NULL AND started_at IS NOT NULL)"
            " OR (NOT active AND reason IS NULL AND started_at IS NULL)",
            name=op.f("ck_maintenance_active_state"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_maintenance_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_maintenance")),
        sa.UniqueConstraint("org_id", name=op.f("uq_maintenance_org_id")),
    )
    op.create_index(op.f("ix_maintenance_org_id"), "maintenance", ["org_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_maintenance_org_id"), table_name="maintenance")
    op.drop_table("maintenance")

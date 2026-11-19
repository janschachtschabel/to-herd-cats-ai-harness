"""m9 storage tombstone (plan M9 task 1, decision 4): `storage_tombstone`, one row per
file whose last attachment was deleted; the due loop removes the file after 48 hours
if nothing uses it again, so a backup's snapshot finds every file of its rows.

Expand only: one new table. The previous release neither reads nor writes it (it
still removes unused files at once, which a backup of this release tolerates: its
snapshot is taken by this release's processes only after the rollout).

Revision ID: c4f1a7e2b9d3
Revises: 8e2a4c6b0d1f
Create Date: 2026-11-26 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4f1a7e2b9d3"
down_revision: str | None = "8e2a4c6b0d1f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_tombstone",
        sa.Column("storage_key", sa.String(length=300), nullable=False),
        sa.Column("buried_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_storage_tombstone_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_storage_tombstone")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_storage_tombstone_storage_key")),
    )
    op.create_index(op.f("ix_storage_tombstone_org_id"), "storage_tombstone", ["org_id"])
    op.create_index(op.f("ix_storage_tombstone_buried_at"), "storage_tombstone", ["buried_at"])


def downgrade() -> None:
    op.drop_index(op.f("ix_storage_tombstone_buried_at"), table_name="storage_tombstone")
    op.drop_index(op.f("ix_storage_tombstone_org_id"), table_name="storage_tombstone")
    op.drop_table("storage_tombstone")

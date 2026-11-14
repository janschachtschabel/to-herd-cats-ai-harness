"""m6 approval outcome (plan M6 decision 4): `approval.outcome`, what became of an
approved call (`ran` or `stale`), so the API reports a stale release instead of a
reader deriving it from the run's journal.

Backward compatible: a nullable column and a check that only holds it to its values;
the previous release neither reads nor writes it.

Revision ID: e5a7c9d1f3b5
Revises: d4f6b8c0e2a3
Create Date: 2026-11-14 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5a7c9d1f3b5"
down_revision: str | None = "d4f6b8c0e2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("approval", sa.Column("outcome", sa.String(length=16), nullable=True))
    op.create_check_constraint(
        op.f("ck_approval_outcome"),
        "approval",
        "outcome IS NULL OR (state = 'approved' AND outcome IN ('ran', 'stale'))",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_approval_outcome"), "approval", type_="check")
    op.drop_column("approval", "outcome")

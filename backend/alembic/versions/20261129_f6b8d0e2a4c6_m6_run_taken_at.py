"""m6 run taken_at (module review M6, finding 4): `run.taken_at`, when the run's
current take-up began; every claim sets it. The stuck-run gauge (`herd_runs_stuck`)
counts a take-up older than any run may run, instead of the first start
(`started_at`), which made a run resumed after a long wait for a person count as stuck.

Expand-only: a nullable column without a default. The previous release neither reads
nor writes it; its claims leave it as it was. While both run, the gauge of this
release counts a run that only the previous release took up by its lease alone (a
NULL `taken_at` is never overdue), and one it took up again after a take-up of this
release by that older `taken_at` (it may count as stuck for that while).

Revision ID: f6b8d0e2a4c6
Revises: e5a7c9d1f3b5
Create Date: 2026-11-14 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6b8d0e2a4c6"
down_revision: str | None = "e5a7c9d1f3b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("run", sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("run", "taken_at")

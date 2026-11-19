"""m9 backup offsite (plan M9 task 3, decisions 8 and 11): `backup_run.offsite_state`
(`off`, `ok`, `failed`), whether the archive went to the restic repository.

Expand only: a column with a constant default (no rewrite). The previous release
neither reads nor writes it; its rows get `off`.

Revision ID: e1c9f3b7a5d2
Revises: d8b2e5a1c7f4
Create Date: 2026-11-28 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e1c9f3b7a5d2"
down_revision: str | None = "d8b2e5a1c7f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backup_run",
        sa.Column("offsite_state", sa.String(length=16), server_default="off", nullable=False),
    )
    op.create_check_constraint(
        op.f("ck_backup_run_offsite_state"),
        "backup_run",
        "offsite_state IN ('off', 'ok', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_backup_run_offsite_state"), "backup_run", type_="check")
    op.drop_column("backup_run", "offsite_state")

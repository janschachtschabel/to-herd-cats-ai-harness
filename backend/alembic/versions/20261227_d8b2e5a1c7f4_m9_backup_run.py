"""m9 backup run (plan M9 task 1, decision 11): `backup_run`, one row per backup
(trigger, state, times, the archive's name, size and SHA-256, an error code).

Expand only: one new table. The previous release neither reads nor writes it.

Revision ID: d8b2e5a1c7f4
Revises: c4f1a7e2b9d3
Create Date: 2026-11-27 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8b2e5a1c7f4"
down_revision: str | None = "c4f1a7e2b9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backup_run",
        sa.Column("trigger", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archive", sa.String(length=120), nullable=True),
        sa.Column("bytes", sa.BigInteger(), nullable=True),
        sa.Column("archive_sha256", sa.String(length=64), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "trigger IN ('schedule', 'cli', 'admin', 'pre_restore')",
            name=op.f("ck_backup_run_trigger"),
        ),
        sa.CheckConstraint(
            "state IN ('running', 'ok', 'failed', 'interrupted')",
            name=op.f("ck_backup_run_state"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_backup_run_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_backup_run")),
    )
    op.create_index(op.f("ix_backup_run_org_id"), "backup_run", ["org_id"])
    op.create_index("ix_backup_run_started_at", "backup_run", ["started_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_backup_run_started_at", table_name="backup_run")
    op.drop_index(op.f("ix_backup_run_org_id"), table_name="backup_run")
    op.drop_table("backup_run")

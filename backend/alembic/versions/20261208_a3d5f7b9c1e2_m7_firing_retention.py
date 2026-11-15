"""m7 firing retention (plan M7 task 11): an index on `automation_firing.fired_at`,
so the worker finds the terms older than the retention without reading the log.

Expand only: one index. The previous release neither reads nor needs it; it only
adds to the cost of writing a term.

Revision ID: a3d5f7b9c1e2
Revises: 8c4e1a7f3b26
Create Date: 2026-11-15 12:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a3d5f7b9c1e2"
down_revision: str | None = "8c4e1a7f3b26"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        op.f("ix_automation_firing_fired_at"), "automation_firing", ["fired_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_firing_fired_at"), table_name="automation_firing")

"""m8 fresh start (module review M8 3, finding H2): `conversation.fresh_start_at` is
where the person started her DM alone with an agent afresh ("Neu beginnen"); runs
after it get no history from before it, so the personal mark of what came before
ends for them.

Expand only: a nullable column (no rewrite). The previous release neither reads nor
writes it: during a rollout its workers still give runs the whole history (the mark
then holds as before) until they are replaced.

Revision ID: f3a7c9e1b5d8
Revises: 8fc798e7f305
Create Date: 2026-11-30 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a7c9e1b5d8"
down_revision: str | None = "8fc798e7f305"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("fresh_start_at", sa.DateTime(timezone=True)))


def downgrade() -> None:
    op.drop_column("conversation", "fresh_start_at")

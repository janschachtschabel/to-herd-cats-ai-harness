"""m8 level four (plan M8 task 7): an agent's autonomy level may be 4 (acting outside:
external write tools, always with a person's release).

Expand only: the check on `agent.level` widens from 1–3 to 1–4. The previous release
writes 1 to 3 only and reads the level as a number, so it works on either side.

Revision ID: f4c6e8a0b2d4
Revises: e5c1a7d3b9f2
Create Date: 2026-11-16 18:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f4c6e8a0b2d4"
down_revision: str | None = "e5c1a7d3b9f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(op.f("ck_agent_level"), "agent", type_="check")
    op.create_check_constraint(op.f("ck_agent_level"), "agent", "level BETWEEN 1 AND 4")


def downgrade() -> None:
    op.execute("UPDATE agent SET level = 3 WHERE level > 3")
    op.drop_constraint(op.f("ck_agent_level"), "agent", type_="check")
    op.create_check_constraint(op.f("ck_agent_level"), "agent", "level BETWEEN 1 AND 3")

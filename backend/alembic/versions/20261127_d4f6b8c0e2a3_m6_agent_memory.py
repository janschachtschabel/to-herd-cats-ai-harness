"""m6 agent memory (plan M6 task 9, decision 10): `agent_memory`, which wiki page is
an agent's memory in a space.

Backward compatible: a new table only; the previous release reads none of it (its
memory pages are ordinary pages to it).

Revision ID: d4f6b8c0e2a3
Revises: c3e5a7b9d1f2
Create Date: 2026-11-14 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4f6b8c0e2a3"
down_revision: str | None = "c3e5a7b9d1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_memory",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_memory_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_agent_memory_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_agent_memory_page_id_page"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_agent_memory_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_id", "space_id", name=op.f("pk_agent_memory")),
        sa.UniqueConstraint("page_id", name=op.f("uq_agent_memory_page_id")),
    )
    op.create_index(op.f("ix_agent_memory_org_id"), "agent_memory", ["org_id"], unique=False)
    op.create_index("ix_agent_memory_space_id", "agent_memory", ["space_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_memory_space_id", table_name="agent_memory")
    op.drop_index(op.f("ix_agent_memory_org_id"), table_name="agent_memory")
    op.drop_table("agent_memory")

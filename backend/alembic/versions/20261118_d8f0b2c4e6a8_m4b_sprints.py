"""m4b sprints: a space's sprints (`sprint`) and a ticket's sprint (`work_item.sprint_id`).

- At most one sprint per space is active: the unique partial index
  `uq_sprint_space_id_active`, whatever code writes it.
- A ticket's sprint is one of its own space: the foreign key over (sprint, space)
  refers to the sprint's (id, space_id).
- A closed sprint has its tally, an open one none (CHECK `tally`).

Backward compatible: a new table and a nullable column; the previous release neither
reads nor writes them (a ticket it writes keeps its sprint).

Revision ID: d8f0b2c4e6a8
Revises: c7e9a1b3d5f7
Create Date: 2026-11-18 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d8f0b2c4e6a8"
down_revision: str | None = "c7e9a1b3d5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sprint",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("goal", sa.String(length=500), nullable=False),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("planned_count", sa.Integer(), nullable=True),
        sa.Column("done_count", sa.Integer(), nullable=True),
        sa.Column("carried_count", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(state = 'closed') = (planned_count IS NOT NULL)"
            " AND (planned_count IS NULL) = (done_count IS NULL)"
            " AND (planned_count IS NULL) = (carried_count IS NULL)",
            name=op.f("ck_sprint_tally"),
        ),
        sa.CheckConstraint("char_length(goal) <= 500", name=op.f("ck_sprint_goal_length")),
        sa.CheckConstraint(
            "char_length(name) BETWEEN 1 AND 80", name=op.f("ck_sprint_name_length")
        ),
        sa.CheckConstraint("ends_on >= starts_on", name=op.f("ck_sprint_dates")),
        sa.CheckConstraint(
            "state IN ('planned', 'active', 'closed')", name=op.f("ck_sprint_state")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_sprint_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["space.id"], name=op.f("fk_sprint_space_id_space"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sprint")),
        sa.UniqueConstraint("id", "space_id", name=op.f("uq_sprint_id_space_id")),
    )
    op.create_index(op.f("ix_sprint_org_id"), "sprint", ["org_id"], unique=False)
    op.create_index("ix_sprint_space_id_state", "sprint", ["space_id", "state"], unique=False)
    op.create_index(
        "uq_sprint_space_id_active",
        "sprint",
        ["space_id"],
        unique=True,
        postgresql_where=sa.text("state = 'active'"),
    )
    op.add_column("work_item", sa.Column("sprint_id", sa.UUID(), nullable=True))
    op.create_index("ix_work_item_sprint_id", "work_item", ["sprint_id"], unique=False)
    op.create_foreign_key(
        "fk_work_item_sprint_id_sprint",
        "work_item",
        "sprint",
        ["sprint_id", "space_id"],
        ["id", "space_id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_work_item_sprint_id_sprint", "work_item", type_="foreignkey")
    op.drop_index("ix_work_item_sprint_id", table_name="work_item")
    op.drop_column("work_item", "sprint_id")
    op.drop_index(
        "uq_sprint_space_id_active",
        table_name="sprint",
        postgresql_where=sa.text("state = 'active'"),
    )
    op.drop_index("ix_sprint_space_id_state", table_name="sprint")
    op.drop_index(op.f("ix_sprint_org_id"), table_name="sprint")
    op.drop_table("sprint")

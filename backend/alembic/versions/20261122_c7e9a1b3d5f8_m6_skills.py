"""m6 skills (plan M6 task 9, decision 11): the tables `skill` (organisation-wide or of
one space, name unique per scope), `skill_version` (every change of description or
content) and `agent_skill` (which skills an agent may use).

Backward compatible: new tables only; the previous release reads none of them.

Revision ID: c7e9a1b3d5f8
Revises: f2c4e6a8b0d1
Create Date: 2026-11-22 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c7e9a1b3d5f8"
down_revision: str | None = "f2c4e6a8b0d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill",
        sa.Column("space_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("author_type IN ('user', 'agent')", name=op.f("ck_skill_author_type")),
        sa.CheckConstraint("state IN ('active', 'archived')", name=op.f("ck_skill_state")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_skill_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"], ["space.id"], name=op.f("fk_skill_space_id_space"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill")),
    )
    op.create_index(op.f("ix_skill_org_id"), "skill", ["org_id"], unique=False)
    op.create_index("ix_skill_space_id", "skill", ["space_id"], unique=False)
    op.create_index(
        "uq_skill_org_name",
        "skill",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("space_id IS NULL"),
    )
    op.create_index(
        "uq_skill_space_name",
        "skill",
        ["org_id", "space_id", "name"],
        unique=True,
        postgresql_where=sa.text("space_id IS NOT NULL"),
    )
    op.create_table(
        "agent_skill",
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_agent_skill_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_agent_skill_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_agent_skill_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("agent_id", "skill_id", name=op.f("pk_agent_skill")),
    )
    op.create_index(op.f("ix_agent_skill_org_id"), "agent_skill", ["org_id"], unique=False)
    op.create_index("ix_agent_skill_skill_id", "agent_skill", ["skill_id"], unique=False)
    op.create_table(
        "skill_version",
        sa.Column("skill_id", sa.UUID(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "author_type IN ('user', 'agent')", name=op.f("ck_skill_version_author_type")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_skill_version_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_skill_version_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_version")),
    )
    op.create_index(op.f("ix_skill_version_org_id"), "skill_version", ["org_id"], unique=False)
    op.create_index(
        "uq_skill_version_skill_id_number", "skill_version", ["skill_id", "number"], unique=True
    )


def downgrade() -> None:
    op.drop_index("uq_skill_version_skill_id_number", table_name="skill_version")
    op.drop_index(op.f("ix_skill_version_org_id"), table_name="skill_version")
    op.drop_table("skill_version")
    op.drop_index("ix_agent_skill_skill_id", table_name="agent_skill")
    op.drop_index(op.f("ix_agent_skill_org_id"), table_name="agent_skill")
    op.drop_table("agent_skill")
    op.drop_index(
        "uq_skill_space_name", table_name="skill", postgresql_where=sa.text("space_id IS NOT NULL")
    )
    op.drop_index(
        "uq_skill_org_name", table_name="skill", postgresql_where=sa.text("space_id IS NULL")
    )
    op.drop_index("ix_skill_space_id", table_name="skill")
    op.drop_index(op.f("ix_skill_org_id"), table_name="skill")
    op.drop_table("skill")

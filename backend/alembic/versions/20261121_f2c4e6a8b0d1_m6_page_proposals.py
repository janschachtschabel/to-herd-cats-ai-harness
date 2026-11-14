"""m6 page proposals (plan M6 task 5): the table `page_proposal`, the space setting
`agent_write_policy` (`propose` by default), versions written for an agent (source
`agent`, `run_id`), and the notification reason `proposal`.

Expand only: a new table, a nullable column, a column with a default, and two CHECKs
widened. The previous release never writes the new values; it does not read the new
table or columns.

Revision ID: f2c4e6a8b0d1
Revises: a3b5d7f9c1e3
Create Date: 2026-11-14 03:07:26.347121
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2c4e6a8b0d1"
down_revision: str | None = "a3b5d7f9c1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_proposal",
        sa.Column("space_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("page_id", sa.UUID(), nullable=True),
        sa.Column("parent_id", sa.UUID(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=True),
        sa.Column("base_version", sa.Integer(), nullable=True),
        sa.Column("base_content_md", sa.Text(), nullable=True),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("author_type", sa.String(length=16), nullable=False),
        sa.Column("author_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("decided_by_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_reason", sa.String(length=300), nullable=True),
        sa.Column("result_version_id", sa.UUID(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "(kind = 'change' AND page_id IS NOT NULL AND parent_id IS NULL AND title IS NULL AND base_version IS NOT NULL AND base_content_md IS NOT NULL) OR (kind = 'new' AND title IS NOT NULL AND base_version IS NULL AND base_content_md IS NULL AND (page_id IS NULL OR state = 'accepted'))",
            name=op.f("ck_page_proposal_shape"),
        ),
        sa.CheckConstraint(
            "(state = 'open') = (decided_at IS NULL) AND (state = 'rejected' OR decision_reason IS NULL)",
            name=op.f("ck_page_proposal_decision"),
        ),
        sa.CheckConstraint(
            "author_type IN ('user', 'agent')", name=op.f("ck_page_proposal_author_type")
        ),
        sa.CheckConstraint("kind IN ('change', 'new')", name=op.f("ck_page_proposal_kind")),
        sa.CheckConstraint(
            "state IN ('open', 'accepted', 'rejected', 'withdrawn')",
            name=op.f("ck_page_proposal_state"),
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"], ["app_user.id"], name=op.f("fk_page_proposal_decided_by_id_app_user")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_page_proposal_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"], ["page.id"], name=op.f("fk_page_proposal_page_id_page"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["page.id"],
            name=op.f("fk_page_proposal_parent_id_page"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["result_version_id"],
            ["page_version.id"],
            name=op.f("fk_page_proposal_result_version_id_page_version"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_page_proposal_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_proposal")),
    )
    op.create_index(op.f("ix_page_proposal_org_id"), "page_proposal", ["org_id"], unique=False)
    op.create_index("ix_page_proposal_page_id", "page_proposal", ["page_id"], unique=False)
    op.create_index("ix_page_proposal_parent_id", "page_proposal", ["parent_id"], unique=False)
    op.create_index(
        "ix_page_proposal_result_version_id", "page_proposal", ["result_version_id"], unique=False
    )
    op.create_index(
        "ix_page_proposal_space_id_id", "page_proposal", ["space_id", "id"], unique=False
    )
    op.add_column("page_version", sa.Column("run_id", sa.UUID(), nullable=True))
    op.add_column(
        "space",
        sa.Column(
            "agent_write_policy", sa.String(length=16), server_default="propose", nullable=False
        ),
    )
    op.create_check_constraint(
        op.f("ck_space_agent_write_policy"), "space", "agent_write_policy IN ('propose', 'direct')"
    )
    _check("page_version", "source", SOURCES + ("agent",))
    _check("notification", "reason", REASONS + ("proposal",))


SOURCES = ("human", "import", "restore", "collab")
REASONS = ("mention", "reply", "assignment", "ticket_comment")


def _check(table: str, column: str, values: tuple[str, ...]) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{column}"), table, type_="check")
    allowed = ", ".join(f"'{v}'" for v in values)
    op.create_check_constraint(op.f(f"ck_{table}_{column}"), table, f"{column} IN ({allowed})")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE reason = 'proposal'")
    _check("notification", "reason", REASONS)
    op.execute("UPDATE page_version SET source = 'human' WHERE source = 'agent'")
    _check("page_version", "source", SOURCES)
    op.drop_constraint(op.f("ck_space_agent_write_policy"), "space", type_="check")
    op.drop_column("space", "agent_write_policy")
    op.drop_column("page_version", "run_id")
    op.drop_index("ix_page_proposal_space_id_id", table_name="page_proposal")
    op.drop_index("ix_page_proposal_result_version_id", table_name="page_proposal")
    op.drop_index("ix_page_proposal_parent_id", table_name="page_proposal")
    op.drop_index("ix_page_proposal_page_id", table_name="page_proposal")
    op.drop_index(op.f("ix_page_proposal_org_id"), table_name="page_proposal")
    op.drop_table("page_proposal")

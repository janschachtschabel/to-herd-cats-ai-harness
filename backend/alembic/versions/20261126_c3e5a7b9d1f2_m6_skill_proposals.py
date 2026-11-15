"""m6 skill proposals (plan M6 task 9): `skill_proposal` (a new skill or a change to
one, made by an agent's run, decided by whoever manages skills in its scope), and
notifications about one (`notification.skill_proposal_id`, reason `skill_proposal`).

Expand only: a new table, a nullable column, widened CHECKs, new indexes. The
previous release never writes the new values; it reads a notification with reason
`skill_proposal` only once this release wrote one (rolling update note, docs).

Revision ID: c3e5a7b9d1f2
Revises: b2d4f6a8c0e1
Create Date: 2026-11-14 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3e5a7b9d1f2"
down_revision: str | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFY = (
    "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal', 'approval', 'question',"
    " 'run_stopped'"
)
TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND space_id IS NULL) OR (message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NOT NULL AND space_id IS NOT NULL)"
)
WIDER_TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NOT NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NOT NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NOT NULL)"
)


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.create_table(
        "skill_proposal",
        sa.Column("space_id", sa.UUID(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("skill_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=64), nullable=True),
        sa.Column("base_number", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(length=1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
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
        sa.CheckConstraint("kind IN ('change', 'new')", name=op.f("ck_skill_proposal_kind")),
        sa.CheckConstraint(
            "state IN ('open', 'accepted', 'rejected')", name=op.f("ck_skill_proposal_state")
        ),
        sa.CheckConstraint(
            "author_type IN ('user', 'agent')", name=op.f("ck_skill_proposal_author_type")
        ),
        sa.CheckConstraint(
            "(kind = 'change' AND skill_id IS NOT NULL AND name IS NULL"
            " AND base_number IS NOT NULL)"
            " OR (kind = 'new' AND name IS NOT NULL AND base_number IS NULL"
            " AND (skill_id IS NULL OR state = 'accepted'))",
            name=op.f("ck_skill_proposal_shape"),
        ),
        sa.CheckConstraint(
            "(state = 'open') = (decided_at IS NULL)"
            " AND (state = 'rejected' OR decision_reason IS NULL)",
            name=op.f("ck_skill_proposal_decision"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_skill_proposal_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_skill_proposal_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skill.id"],
            name=op.f("fk_skill_proposal_skill_id_skill"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_id"],
            ["app_user.id"],
            name=op.f("fk_skill_proposal_decided_by_id_app_user"),
        ),
        sa.ForeignKeyConstraint(
            ["result_version_id"],
            ["skill_version.id"],
            name=op.f("fk_skill_proposal_result_version_id_skill_version"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_proposal")),
    )
    op.create_index(op.f("ix_skill_proposal_org_id"), "skill_proposal", ["org_id"])
    op.create_index("ix_skill_proposal_space_id", "skill_proposal", ["space_id"])
    op.create_index("ix_skill_proposal_skill_id", "skill_proposal", ["skill_id"])
    op.create_index("ix_skill_proposal_result_version_id", "skill_proposal", ["result_version_id"])
    op.add_column("notification", sa.Column("skill_proposal_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notification_skill_proposal_id_skill_proposal"),
        "notification",
        "skill_proposal",
        ["skill_proposal_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notification_skill_proposal_id", "notification", ["skill_proposal_id"])
    op.create_index(
        "uq_notification_skill_proposal",
        "notification",
        ["user_id", "skill_proposal_id", "reason"],
        unique=True,
        postgresql_where=sa.text("skill_proposal_id IS NOT NULL"),
    )
    _replace_check("notification", "target", WIDER_TARGET)
    _replace_check("notification", "reason", f"reason IN ({NOTIFY}, 'skill_proposal')")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE skill_proposal_id IS NOT NULL")
    _replace_check("notification", "reason", f"reason IN ({NOTIFY})")
    _replace_check("notification", "target", TARGET)
    op.drop_index(
        "uq_notification_skill_proposal",
        table_name="notification",
        postgresql_where=sa.text("skill_proposal_id IS NOT NULL"),
    )
    op.drop_index("ix_notification_skill_proposal_id", table_name="notification")
    op.drop_constraint(
        op.f("fk_notification_skill_proposal_id_skill_proposal"),
        "notification",
        type_="foreignkey",
    )
    op.drop_column("notification", "skill_proposal_id")
    op.drop_index("ix_skill_proposal_result_version_id", table_name="skill_proposal")
    op.drop_index("ix_skill_proposal_skill_id", table_name="skill_proposal")
    op.drop_index("ix_skill_proposal_space_id", table_name="skill_proposal")
    op.drop_index(op.f("ix_skill_proposal_org_id"), table_name="skill_proposal")
    op.drop_table("skill_proposal")

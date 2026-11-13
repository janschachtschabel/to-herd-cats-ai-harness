"""m3 dm: direct messages (kind `dm`, its participants and its key) and the admin's
audited inspection of them.

Backward compatible: a nullable column, a wider kind check and new tables; the
previous release knows only channels and keeps working.

Revision ID: d5f7b9c1e3a5
Revises: c3e5a7b9d1f3
Create Date: 2026-11-13 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5f7b9c1e3a5"
down_revision: str | None = "c3e5a7b9d1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("conversation", sa.Column("dm_key", sa.String(length=64), nullable=True))
    op.drop_constraint(op.f("ck_conversation_kind"), "conversation", type_="check")
    op.create_check_constraint(
        op.f("ck_conversation_kind"), "conversation", "kind IN ('channel', 'dm')"
    )
    op.create_check_constraint(
        op.f("ck_conversation_dm_fields"),
        "conversation",
        "(kind = 'dm') = (dm_key IS NOT NULL)"
        " AND (kind <> 'dm' OR (space_id IS NULL AND name IS NULL AND topic IS NULL))",
    )
    op.create_unique_constraint(
        op.f("uq_conversation_org_id_dm_key"), "conversation", ["org_id", "dm_key"]
    )
    op.create_table(
        "conversation_participant",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=False),
        sa.Column("principal_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "principal_type IN ('user')", name=op.f("ck_conversation_participant_principal_type")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_conversation_participant_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_conversation_participant_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id",
            "principal_type",
            "principal_id",
            name=op.f("pk_conversation_participant"),
        ),
    )
    op.create_index(
        "ix_conversation_participant_principal",
        "conversation_participant",
        ["principal_type", "principal_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_conversation_participant_org_id"),
        "conversation_participant",
        ["org_id"],
        unique=False,
    )
    op.create_table(
        "dm_inspection",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "char_length(reason) <= 500", name=op.f("ck_dm_inspection_reason_length")
        ),
        sa.CheckConstraint("expires_at > granted_at", name=op.f("ck_dm_inspection_expiry")),
        sa.ForeignKeyConstraint(
            ["admin_id"], ["app_user.id"], name=op.f("fk_dm_inspection_admin_id_app_user")
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_dm_inspection_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_dm_inspection_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dm_inspection")),
    )
    op.create_index(
        "ix_dm_inspection_conversation_id", "dm_inspection", ["conversation_id"], unique=False
    )
    op.create_index(op.f("ix_dm_inspection_org_id"), "dm_inspection", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_dm_inspection_org_id"), table_name="dm_inspection")
    op.drop_index("ix_dm_inspection_conversation_id", table_name="dm_inspection")
    op.drop_table("dm_inspection")
    op.drop_index(op.f("ix_conversation_participant_org_id"), table_name="conversation_participant")
    op.drop_index("ix_conversation_participant_principal", table_name="conversation_participant")
    op.drop_table("conversation_participant")
    op.execute(sa.text("DELETE FROM conversation WHERE kind = 'dm'"))
    op.drop_constraint(op.f("uq_conversation_org_id_dm_key"), "conversation", type_="unique")
    op.drop_constraint(op.f("ck_conversation_dm_fields"), "conversation", type_="check")
    op.drop_constraint(op.f("ck_conversation_kind"), "conversation", type_="check")
    op.create_check_constraint(op.f("ck_conversation_kind"), "conversation", "kind IN ('channel')")
    op.drop_column("conversation", "dm_key")

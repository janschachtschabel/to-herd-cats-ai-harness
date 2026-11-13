"""m3 notifications: what the activity view lists (reasons `mention` and `reply`),
unique per person, message and reason, which makes the handler that writes them
idempotent.

Backward compatible: a new table only.

Revision ID: f7b9d1e3a5c7
Revises: e6a8c0d2f4b6
Create Date: 2026-11-13 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f7b9d1e3a5c7"
down_revision: str | None = "e6a8c0d2f4b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notification",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=16), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("reason IN ('mention', 'reply')", name=op.f("ck_notification_reason")),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_notification_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["message.id"],
            name=op.f("fk_notification_message_id_message"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_notification_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.id"], name=op.f("fk_notification_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notification")),
        sa.UniqueConstraint(
            "user_id",
            "message_id",
            "reason",
            name=op.f("uq_notification_user_id_message_id_reason"),
        ),
    )
    op.create_index(op.f("ix_notification_org_id"), "notification", ["org_id"], unique=False)
    op.create_index("ix_notification_user_id_id", "notification", ["user_id", "id"], unique=False)
    op.create_index(
        "ix_notification_conversation_id", "notification", ["conversation_id"], unique=False
    )
    op.create_index("ix_notification_message_id", "notification", ["message_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_notification_message_id", table_name="notification")
    op.drop_index("ix_notification_conversation_id", table_name="notification")
    op.drop_index("ix_notification_user_id_id", table_name="notification")
    op.drop_index(op.f("ix_notification_org_id"), table_name="notification")
    op.drop_table("notification")

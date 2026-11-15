"""m3 mentions, reactions, reads: whom a message mentions, reactions by emoji, and
how far each person has read each conversation.

Backward compatible: new tables only.

Revision ID: e6a8c0d2f4b6
Revises: d5f7b9c1e3a5
Create Date: 2026-11-13 19:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6a8c0d2f4b6"
down_revision: str | None = "d5f7b9c1e3a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _org(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["org_id"],
        ["organization.id"],
        name=op.f(f"fk_{table}_org_id_organization"),
        ondelete="CASCADE",
    )


def _message(table: str, column: str = "message_id") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], ["message.id"], name=op.f(f"fk_{table}_{column}_message"), ondelete="CASCADE"
    )


def _user(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["user_id"], ["app_user.id"], name=op.f(f"fk_{table}_user_id_app_user")
    )


def upgrade() -> None:
    op.create_table(
        "message_mention",
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        _message("message_mention"),
        _org("message_mention"),
        _user("message_mention"),
        sa.PrimaryKeyConstraint("message_id", "user_id", name=op.f("pk_message_mention")),
    )
    op.create_index(op.f("ix_message_mention_org_id"), "message_mention", ["org_id"], unique=False)
    op.create_index(
        "ix_message_mention_user_id", "message_mention", ["user_id", "message_id"], unique=False
    )
    op.create_table(
        "reaction",
        sa.Column("message_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("emoji", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        _message("reaction"),
        _org("reaction"),
        _user("reaction"),
        sa.PrimaryKeyConstraint("message_id", "user_id", "emoji", name=op.f("pk_reaction")),
    )
    op.create_index(op.f("ix_reaction_org_id"), "reaction", ["org_id"], unique=False)
    op.create_table(
        "conversation_read",
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("last_read_message_id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_conversation_read_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        _message("conversation_read", "last_read_message_id"),
        _org("conversation_read"),
        _user("conversation_read"),
        sa.PrimaryKeyConstraint("conversation_id", "user_id", name=op.f("pk_conversation_read")),
    )
    op.create_index(
        op.f("ix_conversation_read_org_id"), "conversation_read", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_read_org_id"), table_name="conversation_read")
    op.drop_table("conversation_read")
    op.drop_index(op.f("ix_reaction_org_id"), table_name="reaction")
    op.drop_table("reaction")
    op.drop_index("ix_message_mention_user_id", table_name="message_mention")
    op.drop_index(op.f("ix_message_mention_org_id"), table_name="message_mention")
    op.drop_table("message_mention")

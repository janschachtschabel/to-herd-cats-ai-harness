"""m1 identity: organisation, people, login sessions and the login rate limit.

Revision ID: 86b81d6eb3e8
Revises: 864bb6aadabf
Create Date: 2026-11-12 21:13:02.982939
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "86b81d6eb3e8"
down_revision: str | None = "864bb6aadabf"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organization",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization")),
        sa.UniqueConstraint("slug", name=op.f("uq_organization_slug")),
    )
    op.create_table(
        "rate_limit_hit",
        sa.Column("key", sa.String(length=320), nullable=False),
        sa.Column("hit_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rate_limit_hit")),
    )
    op.create_index(op.f("ix_rate_limit_hit_key"), "rate_limit_hit", ["key"], unique=False)
    op.create_table(
        "app_user",
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("system_role", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("locale", sa.String(length=8), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_app_user_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("org_id", "email", name=op.f("uq_app_user_org_id_email")),
    )
    op.create_index(op.f("ix_app_user_org_id"), "app_user", ["org_id"], unique=False)
    op.create_table(
        "user_session",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_user_session_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_user_session_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_session")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_user_session_token_hash")),
    )
    op.create_index(op.f("ix_user_session_org_id"), "user_session", ["org_id"], unique=False)
    op.create_index(op.f("ix_user_session_user_id"), "user_session", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_session_user_id"), table_name="user_session")
    op.drop_index(op.f("ix_user_session_org_id"), table_name="user_session")
    op.drop_table("user_session")
    op.drop_index(op.f("ix_app_user_org_id"), table_name="app_user")
    op.drop_table("app_user")
    op.drop_index(op.f("ix_rate_limit_hit_key"), table_name="rate_limit_hit")
    op.drop_table("rate_limit_hit")
    op.drop_table("organization")

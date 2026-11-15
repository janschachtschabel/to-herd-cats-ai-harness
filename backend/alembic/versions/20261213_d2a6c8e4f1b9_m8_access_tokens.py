"""m8 access tokens (plan M8 task 1): `access_token` (a person's tokens for `/mcp`,
kept only as the SHA-256 of their clear text) and `mcp_setting` (the organisation's
switch for `mcp.use` and the data location an MCP client counts as).

Expand only: two new tables. The previous release neither reads nor writes them.

Revision ID: d2a6c8e4f1b9
Revises: c4f8a2d6e1b3
Create Date: 2026-11-16 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d2a6c8e4f1b9"
down_revision: str | None = "c4f8a2d6e1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "access_token",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.LargeBinary(), nullable=False),
        sa.Column("space_ids", postgresql.ARRAY(sa.UUID()), nullable=True),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("kind IN ('personal', 'agent')", name=op.f("ck_access_token_kind")),
        sa.CheckConstraint("mode IN ('read', 'write')", name=op.f("ck_access_token_mode")),
        sa.CheckConstraint(
            "octet_length(token_hash) = 32", name=op.f("ck_access_token_token_hash")
        ),
        sa.CheckConstraint(
            "space_ids IS NULL OR cardinality(space_ids) BETWEEN 1 AND 50",
            name=op.f("ck_access_token_space_ids"),
        ),
        sa.CheckConstraint(
            "expires_at <= created_at + interval '365 days'",
            name=op.f("ck_access_token_expiry"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_access_token_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_access_token_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_access_token")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_access_token_token_hash")),
    )
    op.create_index(op.f("ix_access_token_org_id"), "access_token", ["org_id"])
    op.create_index(op.f("ix_access_token_user_id"), "access_token", ["user_id"])
    op.create_table(
        "mcp_setting",
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("data_location", sa.String(length=16), server_default="external", nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "data_location IN ('local', 'eu', 'external')",
            name=op.f("ck_mcp_setting_data_location"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_mcp_setting_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("org_id", name=op.f("pk_mcp_setting")),
    )


def downgrade() -> None:
    op.drop_table("mcp_setting")
    op.drop_index(op.f("ix_access_token_user_id"), table_name="access_token")
    op.drop_index(op.f("ix_access_token_org_id"), table_name="access_token")
    op.drop_table("access_token")

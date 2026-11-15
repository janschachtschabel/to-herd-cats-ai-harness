"""m5 ai connections: the providers admins set up (`ai_connection`, spec 7.1).

Backward compatible: a new table the previous release does not know.

Revision ID: e1a3c5e7f9b1
Revises: d6f8b0c2e4a6
Create Date: 2026-11-16 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e1a3c5e7f9b1"
down_revision: str | None = "d6f8b0c2e4a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_connection",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=True),
        sa.Column("models", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("param_family", sa.String(length=32), nullable=False),
        sa.Column("extra_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("supports_tools", sa.Boolean(), nullable=False),
        sa.Column("data_location", sa.String(length=16), nullable=False),
        sa.Column("max_concurrency", sa.Integer(), nullable=False),
        sa.Column("requests_per_minute", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "kind IN ('openai', 'openai_compatible', 'b_api', 'local')",
            name=op.f("ck_ai_connection_kind"),
        ),
        sa.CheckConstraint(
            "param_family IN ('max_completion_tokens', 'max_tokens')",
            name=op.f("ck_ai_connection_param_family"),
        ),
        sa.CheckConstraint(
            "data_location IN ('local', 'eu', 'external')",
            name=op.f("ck_ai_connection_data_location"),
        ),
        sa.CheckConstraint(
            "purpose IN ('chat', 'embedding', 'both')", name=op.f("ck_ai_connection_purpose")
        ),
        sa.CheckConstraint(
            "secret_ref IS NULL OR secret_ref LIKE 'env:%' OR secret_ref LIKE 'enc:%'",
            name=op.f("ck_ai_connection_secret_ref"),
        ),
        sa.CheckConstraint(
            "max_concurrency BETWEEN 1 AND 100", name=op.f("ck_ai_connection_max_concurrency")
        ),
        sa.CheckConstraint(
            "requests_per_minute BETWEEN 1 AND 100000",
            name=op.f("ck_ai_connection_requests_per_minute"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_ai_connection_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_connection")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_ai_connection_org_id_name")),
    )
    op.create_index(op.f("ix_ai_connection_org_id"), "ai_connection", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_connection_org_id"), table_name="ai_connection")
    op.drop_table("ai_connection")

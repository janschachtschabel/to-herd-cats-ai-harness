"""m5 usage: one record per model call or embedding batch (`usage_record`, spec 7.4)
and optional prices per connection and model (`ai_connection.prices`).

Backward compatible: a new table, and a new column with a default the previous
release need not know (it neither reads nor writes it).

Revision ID: a3c5e7f9b1d3
Revises: f2b4d6f8a0c2
Create Date: 2026-11-16 11:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a3c5e7f9b1d3"
down_revision: str | None = "f2b4d6f8a0c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ai_connection",
        sa.Column(
            "prices",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.create_table(
        "usage_record",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("agent_id", sa.UUID(), nullable=True),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("space_id", sa.UUID(), nullable=True),
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("model", sa.String(length=200), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("tokens_cached", sa.Integer(), nullable=False),
        sa.Column("cost", sa.Numeric(precision=18, scale=8), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "tokens_in >= 0 AND tokens_out >= 0 AND tokens_cached BETWEEN 0 AND tokens_in",
            name=op.f("ck_usage_record_tokens"),
        ),
        sa.CheckConstraint("duration_ms >= 0", name=op.f("ck_usage_record_duration_ms")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_usage_record_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usage_record")),
    )
    op.create_index(op.f("ix_usage_record_org_id"), "usage_record", ["org_id"], unique=False)
    op.create_index(
        "ix_usage_record_org_id_created_at", "usage_record", ["org_id", "created_at"], unique=False
    )
    op.create_index(
        "ix_usage_record_user_id_created_at",
        "usage_record",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index("ix_usage_record_run_id", "usage_record", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_table("usage_record")
    op.drop_column("ai_connection", "prices")

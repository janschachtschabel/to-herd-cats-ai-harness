"""m8 mcp calls (plan M8 task 2, decision 6): `mcp_call`, one row per tool call
through `/mcp` (token, tool, outcome, duration; ids only), read as a token's usage.

Expand only: one new table. The previous release neither reads nor writes it.

Revision ID: e3b5d7f9a1c2
Revises: d7a3c9e5f2b4
Create Date: 2026-11-16 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e3b5d7f9a1c2"
down_revision: str | None = "d7a3c9e5f2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mcp_call",
        sa.Column("token_id", sa.UUID(), nullable=False),
        sa.Column("tool", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('ok', 'refused', 'invalid', 'failed')",
            name=op.f("ck_mcp_call_outcome"),
        ),
        sa.CheckConstraint("duration_ms >= 0", name=op.f("ck_mcp_call_duration_ms")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_mcp_call_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["token_id"],
            ["access_token.id"],
            name=op.f("fk_mcp_call_token_id_access_token"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_call")),
    )
    op.create_index(op.f("ix_mcp_call_org_id"), "mcp_call", ["org_id"])
    op.create_index("ix_mcp_call_token_id_id", "mcp_call", ["token_id", "id"])


def downgrade() -> None:
    op.drop_index("ix_mcp_call_token_id_id", table_name="mcp_call")
    op.drop_index(op.f("ix_mcp_call_org_id"), table_name="mcp_call")
    op.drop_table("mcp_call")

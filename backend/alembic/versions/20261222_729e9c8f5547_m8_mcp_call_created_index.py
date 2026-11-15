"""m8 mcp call created index (module review M8 1, finding 14): `ix_mcp_call_created_at`
for the due loop's retention of `mcp_call` (rows older than 90 days go).

Expand only: an index. The previous release neither needs nor minds it.

Revision ID: 729e9c8f5547
Revises: 60b5e06e0647
Create Date: 2026-11-22 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "729e9c8f5547"
down_revision: str | None = "60b5e06e0647"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_mcp_call_created_at", "mcp_call", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_mcp_call_created_at", table_name="mcp_call")

"""m8 tool approved content (module review M8 1, finding 14):
`mcp_server_tool.approved_description` and `approved_input_schema` keep what an admin
approved, so a `changed` tool shows what changed.

Expand only: two nullable columns. An approved tool whose fingerprint still is the
approved one gets its description and schema (they are what was approved); a changed
one keeps none (what was approved is not known any more). The previous release
neither reads nor writes them; an approval it makes during a rollout keeps none.

Revision ID: a6ce005832fd
Revises: 729e9c8f5547
Create Date: 2026-11-23 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a6ce005832fd"
down_revision: str | None = "729e9c8f5547"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KNOWN = (
    "UPDATE mcp_server_tool SET approved_description = description,"
    " approved_input_schema = input_schema"
    " WHERE approved_fingerprint IS NOT NULL AND approved_fingerprint = fingerprint"
)


def upgrade() -> None:
    op.add_column("mcp_server_tool", sa.Column("approved_description", sa.Text(), nullable=True))
    op.add_column(
        "mcp_server_tool",
        sa.Column("approved_input_schema", postgresql.JSONB(), nullable=True),
    )
    op.execute(KNOWN)


def downgrade() -> None:
    op.drop_column("mcp_server_tool", "approved_input_schema")
    op.drop_column("mcp_server_tool", "approved_description")

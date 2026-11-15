"""m8 tool schema problem (module review M8 1, finding 2): `mcp_server_tool.schema_problem`
says why a tool's input schema cannot be offered to a model (`schema_too_large`,
`schema_unsupported`); such a tool is not usable and not approvable.

Expand only: a nullable column. The previous release neither reads nor writes it; rows
it writes during a rollout have none, and the new code checks their schema itself
before a run offers them.

Revision ID: 60b5e06e0647
Revises: f1afc79e3de4
Create Date: 2026-11-21 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "60b5e06e0647"
down_revision: str | None = "f1afc79e3de4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "mcp_server_tool", sa.Column("schema_problem", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("mcp_server_tool", "schema_problem")

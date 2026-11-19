"""m10 connector purpose (plan M10 task 13a, decision 18): connectors and OAuth clients
name what they are for, `mcp` (everything of M8) or `calendar`. A calendar connector
is personal and serves no MCP server; an OAuth connector connects through an app of its
own purpose (a foreign key on `(oauth_client_id, purpose)` against a new unique
`(id, purpose)` of `oauth_client`).

Expand only: two columns with the server default `mcp`, check constraints that every
existing row meets, a unique constraint and a foreign key. The previous release
(1.0.0) never names the columns; what it writes gets `mcp` and meets every rule.

Revision ID: d5f8a1c3e7b9
Revises: b1c4e7a90d23
Create Date: 2027-01-15 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5f8a1c3e7b9"
down_revision: str | None = "b1c4e7a90d23"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    for table in ("oauth_client", "connector"):
        op.add_column(
            table, sa.Column("purpose", sa.String(16), nullable=False, server_default="mcp")
        )
        op.create_check_constraint(
            op.f(f"ck_{table}_purpose"), table, "purpose IN ('mcp', 'calendar')"
        )
    op.create_unique_constraint(
        op.f("uq_oauth_client_id_purpose"), "oauth_client", ["id", "purpose"]
    )
    op.create_check_constraint(
        op.f("ck_connector_purpose_personal"),
        "connector",
        "purpose = 'mcp' OR (scope = 'personal' AND mcp_server_id IS NULL)",
    )
    op.create_foreign_key(
        op.f("fk_connector_oauth_client_purpose"),
        "connector",
        "oauth_client",
        ["oauth_client_id", "purpose"],
        ["id", "purpose"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(op.f("fk_connector_oauth_client_purpose"), "connector", type_="foreignkey")
    op.drop_constraint(op.f("ck_connector_purpose_personal"), "connector", type_="check")
    op.drop_constraint(op.f("uq_oauth_client_id_purpose"), "oauth_client", type_="unique")
    for table in ("connector", "oauth_client"):
        op.drop_constraint(op.f(f"ck_{table}_purpose"), table, type_="check")
        op.drop_column(table, "purpose")

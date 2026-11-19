"""m10 connector purpose (plan M10 task 13a, decision 18): connectors and OAuth clients
name what they are for, `mcp` (everything of M8) or `calendar`. A calendar connector
is personal and serves no MCP server; an OAuth connector connects through an app of its
own purpose (a foreign key on `(oauth_client_id, purpose)` against a new unique
`(id, purpose)` of `oauth_client`).

An MCP server names only `mcp` connectors and apps (review R13a-8): `mcp_server.purpose`
is a constant `mcp` (CHECK) that composite foreign keys `(connector_id, purpose)` and
`(oauth_client_id, purpose)` compare against a new unique `(id, purpose)` of `connector`
and the one of `oauth_client`. Chosen over a trigger: plain constraints, checked by
PostgreSQL on both sides (a connector's purpose cannot change under a server either),
and `create_all` builds the same schema for the tests. The single-column foreign keys
of M8 stay (dropping them would be a contract).

Expand only: three columns with the server default `mcp`, check constraints that every
existing row meets, two unique constraints and three foreign keys. The previous release
(1.0.0) never names the columns; what it writes gets `mcp` and meets every rule.

Downgrade (R13a-10): below this revision every row would count as `mcp`, so a calendar
access would show among a person's MCP connectors with its secret and a calendar app
become nameable by an MCP server. The downgrade deletes the calendar's rows first,
connectors (their secrets and tokens are in the row; their OAuth flows go by cascade)
before apps; the M10 tables that reference them are dropped by later revisions'
downgrades before this one runs.

Revision ID: d5f8a1c3e7b9
Revises: c5e8a1d4f7b2
Create Date: 2027-01-16 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5f8a1c3e7b9"
down_revision: str | None = "c5e8a1d4f7b2"
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
    op.create_unique_constraint(op.f("uq_connector_id_purpose"), "connector", ["id", "purpose"])
    op.add_column(
        "mcp_server", sa.Column("purpose", sa.String(16), nullable=False, server_default="mcp")
    )
    op.create_check_constraint(op.f("ck_mcp_server_purpose"), "mcp_server", "purpose = 'mcp'")
    for column, target in (("connector_id", "connector"), ("oauth_client_id", "oauth_client")):
        op.create_foreign_key(
            op.f(f"fk_mcp_server_{target}_purpose"),
            "mcp_server",
            target,
            [column, "purpose"],
            ["id", "purpose"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    op.execute("DELETE FROM connector WHERE purpose <> 'mcp'")
    op.execute("DELETE FROM oauth_client WHERE purpose <> 'mcp'")
    for target in ("connector", "oauth_client"):
        op.drop_constraint(
            op.f(f"fk_mcp_server_{target}_purpose"), "mcp_server", type_="foreignkey"
        )
    op.drop_constraint(op.f("ck_mcp_server_purpose"), "mcp_server", type_="check")
    op.drop_column("mcp_server", "purpose")
    op.drop_constraint(op.f("uq_connector_id_purpose"), "connector", type_="unique")
    op.drop_constraint(op.f("fk_connector_oauth_client_purpose"), "connector", type_="foreignkey")
    op.drop_constraint(op.f("ck_connector_purpose_personal"), "connector", type_="check")
    op.drop_constraint(op.f("uq_oauth_client_id_purpose"), "oauth_client", type_="unique")
    for table in ("connector", "oauth_client"):
        op.drop_constraint(op.f(f"ck_{table}_purpose"), table, type_="check")
        op.drop_column(table, "purpose")

"""m8 oauth connectors (plan M8 task 8): OAuth clients of the organisation, flows in
progress, and on `connector` the kind `oauth` with its client, refresh token and
expiry; a personal-scope MCP server may name the OAuth client people connect with.

Expand only: two new tables, new nullable columns with their keys and checks, the
connector's `auth_kind` check widened and `secret_ref` nullable (only an `oauth`
connector that is not connected has none, a check keeps it set for the others). The
previous release writes no `oauth` connector and does not read the new columns.

Revision ID: e5c1a7d3b9f2
Revises: e3b5d7f9a1c2
Create Date: 2026-11-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5c1a7d3b9f2"
down_revision: str | None = "e3b5d7f9a1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _org(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["org_id"],
        ["organization.id"],
        name=op.f(f"fk_{table}_org_id_organization"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    op.create_table(
        "oauth_client",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("authorization_endpoint", sa.String(length=500), nullable=False),
        sa.Column("token_endpoint", sa.String(length=500), nullable=False),
        sa.Column("revocation_endpoint", sa.String(length=500), nullable=True),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_ref", sa.Text(), nullable=True),
        sa.Column("token_auth", sa.String(length=32), nullable=False),
        sa.Column("scopes", sa.String(length=1000), nullable=False),
        sa.Column("resource", sa.String(length=500), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "token_auth IN ('client_secret_basic', 'client_secret_post')",
            name=op.f("ck_oauth_client_token_auth"),
        ),
        sa.CheckConstraint(
            "client_secret_ref IS NULL OR client_secret_ref LIKE 'enc:%'"
            " OR client_secret_ref LIKE 'env:%'",
            name=op.f("ck_oauth_client_client_secret_ref"),
        ),
        _org("oauth_client"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_client")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_oauth_client_org_id_name")),
    )
    op.create_index(op.f("ix_oauth_client_org_id"), "oauth_client", ["org_id"])

    op.alter_column("connector", "secret_ref", existing_type=sa.Text(), nullable=True)
    op.add_column("connector", sa.Column("oauth_client_id", sa.UUID(), nullable=True))
    op.add_column("connector", sa.Column("refresh_token_ref", sa.Text(), nullable=True))
    op.add_column(
        "connector", sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_connector_oauth_client_id_oauth_client"),
        "connector",
        "oauth_client",
        ["oauth_client_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_connector_oauth_client_id"), "connector", ["oauth_client_id"])
    op.drop_constraint(op.f("ck_connector_auth_kind"), "connector", type_="check")
    op.create_check_constraint(
        op.f("ck_connector_auth_kind"), "connector", "auth_kind IN ('bearer', 'header', 'oauth')"
    )
    for name, condition in (
        ("oauth", "(auth_kind = 'oauth') = (oauth_client_id IS NOT NULL)"),
        ("secret_set", "auth_kind = 'oauth' OR secret_ref IS NOT NULL"),
        ("oauth_secret", "auth_kind <> 'oauth' OR secret_ref IS NULL OR secret_ref LIKE 'enc:%'"),
        (
            "refresh_token",
            "refresh_token_ref IS NULL OR (secret_ref IS NOT NULL"
            " AND refresh_token_ref LIKE 'enc:%')",
        ),
        ("token_expires", "auth_kind = 'oauth' OR token_expires_at IS NULL"),
    ):
        op.create_check_constraint(op.f(f"ck_connector_{name}"), "connector", condition)

    op.add_column("mcp_server", sa.Column("oauth_client_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_mcp_server_oauth_client_id_oauth_client"),
        "mcp_server",
        "oauth_client",
        ["oauth_client_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(op.f("ix_mcp_server_oauth_client_id"), "mcp_server", ["oauth_client_id"])
    op.create_check_constraint(
        op.f("ck_mcp_server_oauth_client"),
        "mcp_server",
        "oauth_client_id IS NULL OR connector_scope = 'personal'",
    )

    op.create_table(
        "oauth_flow",
        sa.Column("connector_id", sa.UUID(), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("verifier_ref", sa.Text(), nullable=False),
        sa.Column("redirect_uri", sa.String(length=600), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("verifier_ref LIKE 'enc:%'", name=op.f("ck_oauth_flow_verifier_ref")),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connector.id"],
            name=op.f("fk_oauth_flow_connector_id_connector"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["user_session.id"],
            name=op.f("fk_oauth_flow_session_id_user_session"),
            ondelete="CASCADE",
        ),
        _org("oauth_flow"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oauth_flow")),
        sa.UniqueConstraint("state_hash", name=op.f("uq_oauth_flow_state_hash")),
    )
    for column in ("org_id", "connector_id", "session_id", "expires_at"):
        op.create_index(op.f(f"ix_oauth_flow_{column}"), "oauth_flow", [column])


def downgrade() -> None:
    op.drop_table("oauth_flow")
    op.drop_constraint(op.f("ck_mcp_server_oauth_client"), "mcp_server", type_="check")
    op.drop_index(op.f("ix_mcp_server_oauth_client_id"), table_name="mcp_server")
    op.drop_constraint(
        op.f("fk_mcp_server_oauth_client_id_oauth_client"), "mcp_server", type_="foreignkey"
    )
    op.drop_column("mcp_server", "oauth_client_id")
    for name in ("token_expires", "refresh_token", "oauth_secret", "secret_set", "oauth"):
        op.drop_constraint(op.f(f"ck_connector_{name}"), "connector", type_="check")
    op.execute("DELETE FROM connector WHERE auth_kind = 'oauth'")
    op.drop_constraint(op.f("ck_connector_auth_kind"), "connector", type_="check")
    op.create_check_constraint(
        op.f("ck_connector_auth_kind"), "connector", "auth_kind IN ('bearer', 'header')"
    )
    op.drop_index(op.f("ix_connector_oauth_client_id"), table_name="connector")
    op.drop_constraint(
        op.f("fk_connector_oauth_client_id_oauth_client"), "connector", type_="foreignkey"
    )
    op.drop_column("connector", "token_expires_at")
    op.drop_column("connector", "refresh_token_ref")
    op.drop_column("connector", "oauth_client_id")
    op.alter_column("connector", "secret_ref", existing_type=sa.Text(), nullable=False)
    op.drop_table("oauth_client")

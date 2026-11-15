"""m8 mcp servers (plan M8 task 6): external MCP servers as a tool source, their tools
with fingerprint, classification and approval state, and the server a personal
connector serves.

Expand only: two new tables and a nullable column (with its foreign key, unique index
and check) on `connector`, which the previous release neither reads nor writes.

Revision ID: d7a3c9e5f2b4
Revises: d2a6c8e4f1b9
Create Date: 2026-11-16 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "d7a3c9e5f2b4"
down_revision: str | None = "d2a6c8e4f1b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _base() -> list[sa.Column[object]]:
    return [
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "mcp_server",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("url", sa.String(length=500), nullable=False),
        sa.Column("data_location", sa.String(length=16), nullable=False),
        sa.Column("connector_scope", sa.String(length=16), nullable=False),
        sa.Column("connector_id", sa.UUID(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        *_base(),
        sa.CheckConstraint(
            "(connector_scope = 'shared') = (connector_id IS NOT NULL)",
            name=op.f("ck_mcp_server_connector"),
        ),
        sa.CheckConstraint(
            "connector_scope IN ('none', 'shared', 'personal')",
            name=op.f("ck_mcp_server_connector_scope"),
        ),
        sa.CheckConstraint(
            "data_location IN ('local', 'eu', 'external')",
            name=op.f("ck_mcp_server_data_location"),
        ),
        sa.ForeignKeyConstraint(
            ["connector_id"],
            ["connector.id"],
            name=op.f("fk_mcp_server_connector_id_connector"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_mcp_server_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_server")),
        sa.UniqueConstraint("org_id", "name", name=op.f("uq_mcp_server_org_id_name")),
    )
    op.create_index(op.f("ix_mcp_server_connector_id"), "mcp_server", ["connector_id"])
    op.create_index(op.f("ix_mcp_server_org_id"), "mcp_server", ["org_id"])
    op.create_table(
        "mcp_server_tool",
        sa.Column("server_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("read_only_hint", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("approved_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("missing", sa.Boolean(), nullable=False),
        *_base(),
        sa.CheckConstraint(
            "classification IN ('read', 'write')", name=op.f("ck_mcp_server_tool_classification")
        ),
        sa.CheckConstraint(
            "state <> 'approved' OR approved_fingerprint IS NOT NULL",
            name=op.f("ck_mcp_server_tool_approved"),
        ),
        sa.CheckConstraint(
            "state IN ('pending', 'approved', 'blocked', 'changed')",
            name=op.f("ck_mcp_server_tool_state"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_mcp_server_tool_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["server_id"],
            ["mcp_server.id"],
            name=op.f("fk_mcp_server_tool_server_id_mcp_server"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mcp_server_tool")),
        sa.UniqueConstraint("server_id", "name", name=op.f("uq_mcp_server_tool_server_id_name")),
    )
    op.create_index(op.f("ix_mcp_server_tool_org_id"), "mcp_server_tool", ["org_id"])
    op.create_index("ix_mcp_server_tool_server_id_id", "mcp_server_tool", ["server_id", "id"])
    op.add_column("connector", sa.Column("mcp_server_id", sa.UUID(), nullable=True))
    op.create_index(
        "uq_connector_server_owner",
        "connector",
        ["mcp_server_id", "owner_id"],
        unique=True,
        postgresql_where=sa.text("mcp_server_id IS NOT NULL"),
    )
    op.create_foreign_key(
        op.f("fk_connector_mcp_server_id_mcp_server"),
        "connector",
        "mcp_server",
        ["mcp_server_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_check_constraint(
        op.f("ck_connector_server"), "connector", "mcp_server_id IS NULL OR scope = 'personal'"
    )


def downgrade() -> None:
    op.drop_constraint(op.f("ck_connector_server"), "connector", type_="check")
    op.drop_constraint(
        op.f("fk_connector_mcp_server_id_mcp_server"), "connector", type_="foreignkey"
    )
    op.drop_index("uq_connector_server_owner", table_name="connector")
    op.drop_column("connector", "mcp_server_id")
    op.drop_index("ix_mcp_server_tool_server_id_id", table_name="mcp_server_tool")
    op.drop_index(op.f("ix_mcp_server_tool_org_id"), table_name="mcp_server_tool")
    op.drop_table("mcp_server_tool")
    op.drop_index(op.f("ix_mcp_server_org_id"), table_name="mcp_server")
    op.drop_index(op.f("ix_mcp_server_connector_id"), table_name="mcp_server")
    op.drop_table("mcp_server")

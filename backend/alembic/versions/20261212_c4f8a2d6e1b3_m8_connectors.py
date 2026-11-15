"""m8 connectors (plan M8 task 5): stored credentials for external servers, shared
(the organisation's) or personal (one person's), with a header or bearer secret held
as an `enc:`/`env:` reference.

Expand only: one new table. The previous release neither reads nor writes it.

Revision ID: c4f8a2d6e1b3
Revises: b7e9c1d3f5a7
Create Date: 2026-11-16 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4f8a2d6e1b3"
down_revision: str | None = "b7e9c1d3f5a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "connector",
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("auth_kind", sa.String(length=16), nullable=False),
        sa.Column("header_name", sa.String(length=100), nullable=True),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(auth_kind = 'header') = (header_name IS NOT NULL)",
            name=op.f("ck_connector_header_name"),
        ),
        sa.CheckConstraint(
            "(scope = 'personal') = (owner_id IS NOT NULL)", name=op.f("ck_connector_owner")
        ),
        sa.CheckConstraint(
            "auth_kind IN ('bearer', 'header')", name=op.f("ck_connector_auth_kind")
        ),
        sa.CheckConstraint("scope IN ('shared', 'personal')", name=op.f("ck_connector_scope")),
        sa.CheckConstraint(
            "secret_ref LIKE 'enc:%' OR (scope = 'shared' AND secret_ref LIKE 'env:%')",
            name=op.f("ck_connector_secret_ref"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_connector_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["app_user.id"],
            name=op.f("fk_connector_owner_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connector")),
    )
    op.create_index(op.f("ix_connector_org_id"), "connector", ["org_id"], unique=False)
    op.create_index(
        "uq_connector_personal_name",
        "connector",
        ["owner_id", "name"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NOT NULL"),
    )
    op.create_index(
        "uq_connector_shared_name",
        "connector",
        ["org_id", "name"],
        unique=True,
        postgresql_where=sa.text("owner_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_connector_shared_name", table_name="connector")
    op.drop_index("uq_connector_personal_name", table_name="connector")
    op.drop_index(op.f("ix_connector_org_id"), table_name="connector")
    op.drop_table("connector")

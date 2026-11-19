"""m9 oidc: identity providers (`oidc_provider`), sign-ins in progress (`oidc_flow`)
and the accounts people link (`user_identity`), plan M9 decisions 12 to 15.

Backward compatible: three new tables the previous release neither reads nor writes.

Revision ID: 3d7f1b9c5e2a
Revises: f3a7c9e1b5d8
Create Date: 2026-11-15 18:15:50.213166
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3d7f1b9c5e2a"
down_revision: str | None = "f3a7c9e1b5d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oidc_provider",
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("issuer", sa.String(length=500), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_ref", sa.Text(), nullable=True),
        sa.Column("scopes", sa.String(length=500), nullable=False),
        sa.Column("trust_email", sa.Boolean(), nullable=False),
        sa.Column("allow_signup", sa.Boolean(), nullable=False),
        sa.Column("allowed_domains", postgresql.ARRAY(sa.String(length=253)), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("authorization_endpoint", sa.String(length=500), nullable=True),
        sa.Column("token_endpoint", sa.String(length=500), nullable=True),
        sa.Column("jwks_uri", sa.String(length=500), nullable=True),
        sa.Column("jwks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("jwks_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "client_secret_ref IS NULL OR client_secret_ref LIKE 'enc:%' OR client_secret_ref LIKE 'env:%'",
            name=op.f("ck_oidc_provider_client_secret_ref"),
        ),
        sa.CheckConstraint("kind IN ('google', 'generic')", name=op.f("ck_oidc_provider_kind")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_oidc_provider_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oidc_provider")),
        sa.UniqueConstraint("org_id", "key", name=op.f("uq_oidc_provider_org_id_key")),
    )
    op.create_index(op.f("ix_oidc_provider_org_id"), "oidc_provider", ["org_id"], unique=False)
    op.create_table(
        "user_identity",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_user_identity_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["oidc_provider.id"],
            name=op.f("fk_user_identity_provider_id_oidc_provider"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_user_identity_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_identity")),
        sa.UniqueConstraint(
            "provider_id", "subject", name=op.f("uq_user_identity_provider_id_subject")
        ),
    )
    op.create_index(op.f("ix_user_identity_org_id"), "user_identity", ["org_id"], unique=False)
    op.create_index(
        op.f("ix_user_identity_provider_id"), "user_identity", ["provider_id"], unique=False
    )
    op.create_index(op.f("ix_user_identity_user_id"), "user_identity", ["user_id"], unique=False)
    op.create_table(
        "oidc_flow",
        sa.Column("provider_id", sa.UUID(), nullable=False),
        sa.Column("state_hash", sa.String(length=64), nullable=False),
        sa.Column("binding_hash", sa.String(length=64), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("verifier", sa.String(length=128), nullable=False),
        sa.Column("link_session_id", sa.UUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["link_session_id"],
            ["user_session.id"],
            name=op.f("fk_oidc_flow_link_session_id_user_session"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_oidc_flow_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["oidc_provider.id"],
            name=op.f("fk_oidc_flow_provider_id_oidc_provider"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_oidc_flow")),
        sa.UniqueConstraint("state_hash", name=op.f("uq_oidc_flow_state_hash")),
    )
    op.create_index(op.f("ix_oidc_flow_expires_at"), "oidc_flow", ["expires_at"], unique=False)
    op.create_index(
        op.f("ix_oidc_flow_link_session_id"), "oidc_flow", ["link_session_id"], unique=False
    )
    op.create_index(op.f("ix_oidc_flow_org_id"), "oidc_flow", ["org_id"], unique=False)
    op.create_index(op.f("ix_oidc_flow_provider_id"), "oidc_flow", ["provider_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_oidc_flow_provider_id"), table_name="oidc_flow")
    op.drop_index(op.f("ix_oidc_flow_org_id"), table_name="oidc_flow")
    op.drop_index(op.f("ix_oidc_flow_link_session_id"), table_name="oidc_flow")
    op.drop_index(op.f("ix_oidc_flow_expires_at"), table_name="oidc_flow")
    op.drop_table("oidc_flow")
    op.drop_index(op.f("ix_user_identity_user_id"), table_name="user_identity")
    op.drop_index(op.f("ix_user_identity_provider_id"), table_name="user_identity")
    op.drop_index(op.f("ix_user_identity_org_id"), table_name="user_identity")
    op.drop_table("user_identity")
    op.drop_index(op.f("ix_oidc_provider_org_id"), table_name="oidc_provider")
    op.drop_table("oidc_provider")

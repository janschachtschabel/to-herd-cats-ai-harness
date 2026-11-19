"""m9 totp (plan M9 task 16, Jan's answer J3: an optional second factor):
`user_totp` (one per person: `enc:` secret, confirmed when, last accepted time step),
`totp_recovery_code` (SHA-256 of each unused recovery code) and `sign_in_challenge`
(a sign-in whose first step passed and that waits for the second factor).

Expand only: three new tables. The previous release neither reads nor writes them; it
would sign a person with TOTP in with the password alone (do not run it on this
schema once someone has set TOTP up).

Revision ID: c4d8e1f7a2b9
Revises: a3c5e7f9b2d4
Create Date: 2027-01-06 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e1f7a2b9"
down_revision: str | None = "a3c5e7f9b2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sign_in_challenge",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "method IN ('password', 'oidc')", name=op.f("ck_sign_in_challenge_method")
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_sign_in_challenge_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_sign_in_challenge_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sign_in_challenge")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_sign_in_challenge_token_hash")),
    )
    op.create_index(
        op.f("ix_sign_in_challenge_expires_at"), "sign_in_challenge", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_sign_in_challenge_org_id"), "sign_in_challenge", ["org_id"], unique=False
    )
    op.create_index(
        op.f("ix_sign_in_challenge_user_id"), "sign_in_challenge", ["user_id"], unique=False
    )
    op.create_table(
        "totp_recovery_code",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_totp_recovery_code_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_totp_recovery_code_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_totp_recovery_code")),
        sa.UniqueConstraint(
            "user_id", "code_hash", name=op.f("uq_totp_recovery_code_user_id_code_hash")
        ),
    )
    op.create_index(
        op.f("ix_totp_recovery_code_org_id"), "totp_recovery_code", ["org_id"], unique=False
    )
    op.create_table(
        "user_totp",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("secret_ref", sa.Text(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_step", sa.BigInteger(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_user_totp_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["app_user.id"],
            name=op.f("fk_user_totp_user_id_app_user"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_totp")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_totp_user_id")),
    )
    op.create_index(op.f("ix_user_totp_org_id"), "user_totp", ["org_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_user_totp_org_id"), table_name="user_totp")
    op.drop_table("user_totp")
    op.drop_index(op.f("ix_totp_recovery_code_org_id"), table_name="totp_recovery_code")
    op.drop_table("totp_recovery_code")
    op.drop_index(op.f("ix_sign_in_challenge_user_id"), table_name="sign_in_challenge")
    op.drop_index(op.f("ix_sign_in_challenge_org_id"), table_name="sign_in_challenge")
    op.drop_index(op.f("ix_sign_in_challenge_expires_at"), table_name="sign_in_challenge")
    op.drop_table("sign_in_challenge")

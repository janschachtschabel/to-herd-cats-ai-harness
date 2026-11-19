"""m9 collab grant (plan M9 task 6, decision 16, R14): the collab process acts under
short-lived grants bound to one page and generation instead of the session cookie.

Expand only: one new table. The previous release neither reads nor writes it (no
release has shipped a collab process, so there is no transition layer).

Revision ID: 8fc798e7f305
Revises: e1c9f3b7a5d2
Create Date: 2026-11-29 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8fc798e7f305"
down_revision: str | None = "e1c9f3b7a5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collab_grant",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.UUID(), nullable=True),
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_collab_grant_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_collab_grant_page_id_page"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["user_session.id"],
            name=op.f("fk_collab_grant_session_id_user_session"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collab_grant")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_collab_grant_token_hash")),
    )
    op.create_index(op.f("ix_collab_grant_org_id"), "collab_grant", ["org_id"], unique=False)
    op.create_index(op.f("ix_collab_grant_page_id"), "collab_grant", ["page_id"], unique=False)
    op.create_index(
        op.f("ix_collab_grant_session_id"), "collab_grant", ["session_id"], unique=False
    )
    op.create_index(
        op.f("ix_collab_grant_expires_at"), "collab_grant", ["expires_at"], unique=False
    )


def downgrade() -> None:
    op.drop_table("collab_grant")

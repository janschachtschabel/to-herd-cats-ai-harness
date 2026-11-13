"""m2 collab state: the Yjs state of a page's live-editing session, per generation.

Revision ID: d4a7c2e91b3f
Revises: 56e4721ed3f8
Create Date: 2026-11-13 04:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4a7c2e91b3f"
down_revision: str | None = "56e4721ed3f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "page_collab_state",
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("ydoc", sa.LargeBinary(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_page_collab_state_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_page_collab_state_page_id_page"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("page_id", name=op.f("pk_page_collab_state")),
    )
    op.create_index(
        op.f("ix_page_collab_state_org_id"), "page_collab_state", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_page_collab_state_org_id"), table_name="page_collab_state")
    op.drop_table("page_collab_state")

"""m2 page search: a generated tsvector over title and content, with a GIN index.

Adding the stored column rewrites `page` once; older code never reads it.

Revision ID: c11bf0d84e50
Revises: 94ab8cb957eb
Create Date: 2026-11-13 02:27:14.196335
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c11bf0d84e50"
down_revision: str | None = "94ab8cb957eb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "page",
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('german'::regconfig, title), 'A') || setweight(to_tsvector('simple'::regconfig, title), 'A') || setweight(to_tsvector('german'::regconfig, content_md), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_page_search_tsv", "page", ["search_tsv"], unique=False, postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("ix_page_search_tsv", table_name="page", postgresql_using="gin")
    op.drop_column("page", "search_tsv")

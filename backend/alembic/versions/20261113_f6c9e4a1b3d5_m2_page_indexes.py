"""m2 page indexes: a page's parent and the title prefix of the search (review M2 R19).

`page.parent_id` had an index only behind `space_id`, so the foreign-key check of a
purge scanned `page` once per deleted row; the search's title prefix
(`lower(title) LIKE 'q%'`) had none at all.

Revision ID: f6c9e4a1b3d5
Revises: e5b8d3f0a2c4
Create Date: 2026-11-13 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f6c9e4a1b3d5"
down_revision: str | None = "e5b8d3f0a2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_page_parent_id", "page", ["parent_id"])
    op.create_index(
        "ix_page_title_prefix",
        "page",
        [sa.func.lower(sa.column("title")).label("title_lower")],
        postgresql_ops={"title_lower": "text_pattern_ops"},
    )


def downgrade() -> None:
    op.drop_index("ix_page_title_prefix", table_name="page")
    op.drop_index("ix_page_parent_id", table_name="page")

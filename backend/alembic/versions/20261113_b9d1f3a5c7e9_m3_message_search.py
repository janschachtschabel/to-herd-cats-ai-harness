"""m3 message search: a generated `search_tsv` on messages (German stems of the
Markdown, like a page's content) and a GIN index over the messages search finds
(written by people, not deleted).

Backward compatible: a generated column and an index; the previous release neither
writes nor reads them. Adding a stored generated column rewrites the table once.

Revision ID: b9d1f3a5c7e9
Revises: a8c0e2f4b6d8
Create Date: 2026-11-13 23:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b9d1f3a5c7e9"
down_revision: str | None = "a8c0e2f4b6d8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "message",
        sa.Column(
            "search_tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('german'::regconfig, body_md)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_message_search_tsv",
        "message",
        ["search_tsv"],
        unique=False,
        postgresql_using="gin",
        postgresql_where=sa.text("kind = 'human' AND deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_message_search_tsv", table_name="message", postgresql_using="gin")
    op.drop_column("message", "search_tsv")

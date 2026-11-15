"""m8 mcp writes (plan M8 task 3, decision 3): what a person's AI client writes through
an access token at `/mcp` carries the token's name (`via_token`) on the message, the
ticket, the page proposal and the page version, and a version's source may be `mcp`.

Expand only: four nullable columns and a check constraint that admits one more value.
The previous release neither reads nor writes the columns and never writes `mcp`.

Revision ID: f4c6e8a0b2d3
Revises: a8d2f4b6c1e3
Create Date: 2026-11-16 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4c6e8a0b2d3"
down_revision: str | None = "a8d2f4b6c1e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("message", "work_item", "page_proposal", "page_version")
SOURCES = ("human", "import", "restore", "collab", "agent")


def _source(values: tuple[str, ...]) -> None:
    op.drop_constraint(op.f("ck_page_version_source"), "page_version", type_="check")
    listed = ", ".join(f"'{v}'" for v in values)
    op.create_check_constraint(
        op.f("ck_page_version_source"), "page_version", f"source IN ({listed})"
    )


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column("via_token", sa.String(length=80), nullable=True))
    _source((*SOURCES, "mcp"))


def downgrade() -> None:
    op.execute("UPDATE page_version SET source = 'human' WHERE source = 'mcp'")
    _source(SOURCES)
    for table in TABLES:
        op.drop_column(table, "via_token")

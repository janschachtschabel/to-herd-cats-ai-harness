"""m1 baseline: the root of the migration chain, without operations.

It gives the chain a head from the start, so `/ready` compares a real revision and the
offline rollback render has something to walk. The first tables come in the next revision.

Revision ID: 864bb6aadabf
Revises:
Create Date: 2026-11-12 21:00:19.244552
"""

from collections.abc import Sequence

revision: str = "864bb6aadabf"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

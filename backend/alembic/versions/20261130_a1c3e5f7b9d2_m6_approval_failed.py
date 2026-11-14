"""m6 approval failed (module review M6 2, finding 7): `approval.outcome` may also be
`failed`: the released call ran into its step's lock or statement bound, was rolled
back whole, and its recorded result is the timeout, so it never ran and the run
never comes back to the release.

Expand-only: the check on `outcome` admits one more value; nothing else changes and
no row is rewritten. A pod of the previous release never writes `failed`; one that
reads such an approval (the approval list, the card) fails on it until it is
replaced, as with the other values new in this release (`docs/AGENTEN.md`, Rolling
Update).

Revision ID: a1c3e5f7b9d2
Revises: f6b8d0e2a4c6
Create Date: 2026-11-14 14:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | None = "f6b8d0e2a4c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_approval_outcome"
BEFORE = "outcome IS NULL OR (state = 'approved' AND outcome IN ('ran', 'stale'))"
AFTER = "outcome IS NULL OR (state = 'approved' AND outcome IN ('ran', 'stale', 'failed'))"


def upgrade() -> None:
    op.drop_constraint(op.f(NAME), "approval", type_="check")
    op.create_check_constraint(op.f(NAME), "approval", AFTER)


def downgrade() -> None:
    op.execute("UPDATE approval SET outcome = NULL WHERE outcome = 'failed'")
    op.drop_constraint(op.f(NAME), "approval", type_="check")
    op.create_check_constraint(op.f(NAME), "approval", BEFORE)

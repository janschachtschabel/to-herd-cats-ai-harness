"""m4bfix sprint dates: a sprint's dates are finite and lie between 2000-01-01 and
2100-12-31 (CHECK `dates_range`; module review M4b, finding 1).

The driver sends `date.max` and `date.min` as `infinity` and `-infinity`, and the
sprint list's order key cannot subtract an infinite date (a 500 for the whole space).
Rows the previous release stored outside the range are clamped first (a new version
each), so adding the CHECK cannot fail; clamping keeps `ends_on >= starts_on`.

Backward compatible: the previous release reads both columns as before; a sprint it
would write outside the range is refused by the CHECK instead of breaking the list.

Revision ID: e1b3d5f7a9c0
Revises: d9f1a3c5e7b9
Create Date: 2026-11-19 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "e1b3d5f7a9c0"
down_revision: str | None = "d9f1a3c5e7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CLAMP = """
UPDATE sprint SET
    starts_on = LEAST(GREATEST(starts_on, DATE '2000-01-01'), DATE '2100-12-31'),
    ends_on = LEAST(GREATEST(ends_on, DATE '2000-01-01'), DATE '2100-12-31'),
    version = version + 1
WHERE NOT (starts_on BETWEEN DATE '2000-01-01' AND DATE '2100-12-31'
           AND ends_on BETWEEN DATE '2000-01-01' AND DATE '2100-12-31')
"""

DATES_RANGE = (
    "isfinite(starts_on) AND isfinite(ends_on)"
    " AND starts_on >= DATE '2000-01-01' AND ends_on <= DATE '2100-12-31'"
)


def upgrade() -> None:
    op.execute(CLAMP)
    op.create_check_constraint(op.f("ck_sprint_dates_range"), "sprint", DATES_RANGE)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_sprint_dates_range"), "sprint", type_="check")

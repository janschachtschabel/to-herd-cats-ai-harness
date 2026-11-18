"""m9 totp lock (review M9b F9): a lasting lock on the second factor.

- `user_totp.failures`, `failures_since`: wrong codes counted since the first of the
  current window (24 h); `locked_until`: after ten of them the second factor refuses
  everything until then (an hour).
- the notification reason `totp_locked`: the person's own activity entry about it,
  bound to her account (`account_id`), like `signup`.

Expand: three columns (one with a server default) and a widened check. Widening the
reason check drops the check that 7c2e9a4f1b86 (released) made and creates the wider
one in the same transaction (`contract_of`): every row valid before stays valid. The
previous release never writes the columns or the reason; it knows no TOTP at all, so
it locks nothing, and it would only list a `totp_locked` entry for a person who
manages users while both run during a rollout.

Revision ID: e4b6c8d0f2a3
Revises: b7d0e3f6a9c2
Create Date: 2027-01-12 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e4b6c8d0f2a3"
down_revision: str | None = "b7d0e3f6a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
contract_of = "7c2e9a4f1b86"

NOTIFY = (
    "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal', 'approval', 'question',"
    " 'run_stopped', 'skill_proposal', 'automation', 'review_due', 'signup'"
)


def _replace_reason_check(condition: str) -> None:
    op.drop_constraint(op.f("ck_notification_reason"), "notification", type_="check")
    op.create_check_constraint(op.f("ck_notification_reason"), "notification", condition)


def upgrade() -> None:
    op.add_column(
        "user_totp",
        sa.Column("failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column("user_totp", sa.Column("failures_since", sa.DateTime(timezone=True)))
    op.add_column("user_totp", sa.Column("locked_until", sa.DateTime(timezone=True)))
    op.create_check_constraint(op.f("ck_user_totp_failures"), "user_totp", "failures >= 0")
    _replace_reason_check(f"reason IN ({NOTIFY}, 'totp_locked')")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE reason = 'totp_locked'")
    _replace_reason_check(f"reason IN ({NOTIFY})")
    op.drop_constraint(op.f("ck_user_totp_failures"), "user_totp", type_="check")
    op.drop_column("user_totp", "locked_until")
    op.drop_column("user_totp", "failures_since")
    op.drop_column("user_totp", "failures")

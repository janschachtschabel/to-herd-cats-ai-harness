"""m9 signup approval (plan M9 task 5b, Jan's answer J2: nobody gets in without an
admin's approval).

- `app_user.awaiting_approval_since` (nullable): a self-registered account waiting
  for an admin to approve or reject it; checked to come only with `is_active` false,
  so every "active only" filter keeps the person out. A partial index for the admins'
  list and count.
- `notification.account_id` (nullable, cascading with the account) and the reason
  `signup`: the activity entry that tells the user administrators about a waiting
  account, bound to no conversation; unique per person, account and reason.

Expand only: a nullable column each, new checks and indexes, widened checks. The
previous release never writes the new column or reason; it lists a `signup`
notification without a conversation once this release wrote one, and its admin list
shows a waiting account as deactivated (reactivating it there would let it in
without the approval's audit entry: roll the API out before using self-registration).

Revision ID: 7c2e9a4f1b86
Revises: 5b8d2f6a9c13
Create Date: 2027-01-02 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7c2e9a4f1b86"
down_revision: str | None = "5b8d2f6a9c13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTIFY = (
    "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal', 'approval', 'question',"
    " 'run_stopped', 'skill_proposal', 'automation', 'review_due'"
)
TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NOT NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NOT NULL)"
)
WIDER_TARGET = (
    f"(account_id IS NULL AND ({TARGET}))"
    " OR (account_id IS NOT NULL AND message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NULL AND skill_proposal_id IS NULL AND space_id IS NULL"
    " AND automation_id IS NULL)"
)
WAITING = sa.text("awaiting_approval_since IS NOT NULL")
ACCOUNT = sa.text("account_id IS NOT NULL")


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.add_column(
        "app_user",
        sa.Column("awaiting_approval_since", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f("ck_app_user_awaiting_inactive"),
        "app_user",
        "awaiting_approval_since IS NULL OR NOT is_active",
    )
    op.create_index(
        "ix_app_user_org_id_awaiting", "app_user", ["org_id", "id"], postgresql_where=WAITING
    )
    op.add_column("notification", sa.Column("account_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notification_account_id_app_user"),
        "notification",
        "app_user",
        ["account_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notification_account_id", "notification", ["account_id"])
    op.create_index(
        "uq_notification_account",
        "notification",
        ["user_id", "account_id", "reason"],
        unique=True,
        postgresql_where=ACCOUNT,
    )
    _replace_check("notification", "target", WIDER_TARGET)
    _replace_check("notification", "reason", f"reason IN ({NOTIFY}, 'signup')")


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE account_id IS NOT NULL")
    _replace_check("notification", "reason", f"reason IN ({NOTIFY})")
    _replace_check("notification", "target", TARGET)
    op.drop_index("uq_notification_account", table_name="notification", postgresql_where=ACCOUNT)
    op.drop_index("ix_notification_account_id", table_name="notification")
    op.drop_constraint(
        op.f("fk_notification_account_id_app_user"), "notification", type_="foreignkey"
    )
    op.drop_column("notification", "account_id")
    op.drop_index("ix_app_user_org_id_awaiting", table_name="app_user", postgresql_where=WAITING)
    op.drop_constraint(op.f("ck_app_user_awaiting_inactive"), "app_user", type_="check")
    op.drop_column("app_user", "awaiting_approval_since")

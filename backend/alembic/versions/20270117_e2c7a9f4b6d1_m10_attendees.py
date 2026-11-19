"""m10 attendees (plan M10 task 4, decision 7): invitations and their answers.

- `calendar_event_attendee`: a principal (`user`, `agent`) or an address with a
  display name per row, its role and answer; at most one row per principal and per
  address (letter case aside) on an event; cascading with the event.
- `notification.calendar_event_id` (nullable, cascading with the event): the activity
  entry about an event, bound to no conversation; one per person, event and reason
  (a partial unique index).
- The reason check gains every calendar reason of M10 at once (`invitation`,
  `invite_reply`, `event_reminder`, `event_proposal`, `calendar_sync`); the target
  check gains the event as a target of its own.

This migration only widens: replacing a check drops the check that the released
revision made and creates the wider one in the same transaction (`contract_of`, so
`check_migrations` lets the drops pass). The new reason check admits every reason the
old one admitted, and the new target check is "calendar_event_id IS NULL AND <the old
condition>" or the new event target, so every row valid before stays valid
(`tests/test_event_invitation_schema.py` judges every combination). The previous
release never writes the table, the column or the reasons; while both run during a
rollout it would fail on a calendar notification in a person's activity view
(update every API process before using invitations: `docs/RELEASE-NEXT.md`). From
this release on the activity view lists only the reasons it knows.

Revision ID: e2c7a9f4b6d1
Revises: d5f8a1c3e7b9
Create Date: 2027-01-17 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2c7a9f4b6d1"
down_revision: str | None = "d5f8a1c3e7b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
contract_of = "9e4b6d2f8a17"

_RELEASED = (
    "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal', 'approval', 'question',"
    " 'run_stopped', 'skill_proposal', 'automation', 'review_due', 'signup'"
)
CALENDAR = "'invitation', 'invite_reply', 'event_reminder', 'event_proposal', 'calendar_sync'"
BEFORE_REASONS = f"reason IN ({_RELEASED}, 'totp_locked')"
REASONS = f"reason IN ({_RELEASED}, 'totp_locked', {CALENDAR})"
_TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NOT NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NOT NULL)"
)
BEFORE_TARGET = (
    f"(account_id IS NULL AND ({_TARGET}))"
    " OR (account_id IS NOT NULL AND message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NULL AND skill_proposal_id IS NULL AND space_id IS NULL"
    " AND automation_id IS NULL)"
)
TARGET = (
    f"(calendar_event_id IS NULL AND ({BEFORE_TARGET}))"
    " OR (calendar_event_id IS NOT NULL AND message_id IS NULL AND conversation_id IS NULL"
    " AND proposal_id IS NULL AND skill_proposal_id IS NULL AND space_id IS NULL"
    " AND automation_id IS NULL AND account_id IS NULL)"
)
EVENT = sa.text("calendar_event_id IS NOT NULL")
PRINCIPAL = sa.text("principal_id IS NOT NULL")


def _replace_check(name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_notification_{name}"), "notification", type_="check")
    op.create_check_constraint(op.f(f"ck_notification_{name}"), "notification", condition)


def upgrade() -> None:
    op.create_table(
        "calendar_event_attendee",
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("principal_type", sa.String(length=16), nullable=True),
        sa.Column("principal_id", sa.UUID(), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("name", sa.String(length=200), server_default="", nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("response", sa.String(length=16), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "principal_type IN ('user', 'agent')",
            name=op.f("ck_calendar_event_attendee_principal_type"),
        ),
        sa.CheckConstraint(
            "(principal_type IS NULL) = (principal_id IS NULL)"
            " AND (principal_id IS NULL) = (email IS NOT NULL)",
            name=op.f("ck_calendar_event_attendee_who"),
        ),
        sa.CheckConstraint(
            "role IN ('required', 'optional')", name=op.f("ck_calendar_event_attendee_role")
        ),
        sa.CheckConstraint(
            "response IN ('needs_action', 'accepted', 'tentative', 'declined')",
            name=op.f("ck_calendar_event_attendee_response"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["calendar_event.id"],
            name=op.f("fk_calendar_event_attendee_event_id_calendar_event"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_calendar_event_attendee_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_calendar_event_attendee")),
    )
    op.create_index(
        op.f("ix_calendar_event_attendee_org_id"), "calendar_event_attendee", ["org_id"]
    )
    op.create_index(
        "uq_calendar_event_attendee_principal",
        "calendar_event_attendee",
        ["event_id", "principal_type", "principal_id"],
        unique=True,
        postgresql_where=PRINCIPAL,
    )
    op.create_index(
        "uq_calendar_event_attendee_email",
        "calendar_event_attendee",
        ["event_id", sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )
    op.create_index(
        "ix_calendar_event_attendee_principal",
        "calendar_event_attendee",
        ["principal_id", "event_id"],
        postgresql_where=PRINCIPAL,
    )
    op.add_column("notification", sa.Column("calendar_event_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notification_calendar_event_id_calendar_event"),
        "notification",
        "calendar_event",
        ["calendar_event_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "uq_notification_calendar_event",
        "notification",
        ["user_id", "calendar_event_id", "reason"],
        unique=True,
        postgresql_where=EVENT,
    )
    op.create_index("ix_notification_calendar_event_id", "notification", ["calendar_event_id"])
    _replace_check("reason", REASONS)
    _replace_check("target", TARGET)


def downgrade() -> None:
    op.execute("DELETE FROM notification WHERE calendar_event_id IS NOT NULL")
    op.execute(f"DELETE FROM notification WHERE reason IN ({CALENDAR})")  # noqa: S608 -- constants only
    _replace_check("target", BEFORE_TARGET)
    _replace_check("reason", BEFORE_REASONS)
    op.drop_index("ix_notification_calendar_event_id", table_name="notification")
    op.drop_index("uq_notification_calendar_event", table_name="notification")
    op.drop_constraint(
        op.f("fk_notification_calendar_event_id_calendar_event"), "notification", type_="foreignkey"
    )
    op.drop_column("notification", "calendar_event_id")
    op.drop_table("calendar_event_attendee")

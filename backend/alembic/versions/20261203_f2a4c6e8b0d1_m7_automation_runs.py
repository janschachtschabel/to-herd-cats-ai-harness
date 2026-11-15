"""m7 automation runs (plan M7 task 3): what a fired run needs and what pauses an
automation.

- `automation.failures` (0 by default): runs in a row that did not end `completed`.
- `automation.paused_reason` admits `owner` (the owner lost a right the automation
  needs) and `failing` (three runs in a row did not end `completed`).
- `automation_firing.outcome` admits `skipped_budget` and `skipped_policy`;
  `automation_firing.instruction` (nullable) keeps the instruction a started run was
  given, present exactly for `started`.
- The message trigger function admits a term's system entry at the top level of
  its automation's channel (the root of the thread the run answers in).
- `notification.automation_id` (nullable, cascading with its automation) and the
  reason `automation`: a paused automation's activity entry, bound to no
  conversation.

Expand only: widened checks, nullable columns, a new index and a new check on the
log, which code of the previous release does not write (automations come with this
release). The previous release reads a notification with reason `automation` only
once this release wrote one: its activity view lists it without a conversation
(rolling update note, `docs/AGENTEN.md`).

Revision ID: f2a4c6e8b0d1
Revises: e7a9c1b3d5f7
Create Date: 2026-11-15 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a4c6e8b0d1"
down_revision: str | None = "e7a9c1b3d5f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PAUSED = "(state = 'paused') = (paused_reason IS NOT NULL) AND (paused_reason IS NULL OR {})"
OUTCOMES = "'started', 'skipped_busy', 'skipped_paused_agent'"
NOTIFY = (
    "'mention', 'reply', 'assignment', 'ticket_comment', 'proposal', 'approval', 'question',"
    " 'run_stopped', 'skill_proposal'"
)
TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NOT NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NOT NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NOT NULL)"
)
WIDER_TARGET = (
    "(message_id IS NOT NULL AND conversation_id IS NOT NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NOT NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NOT NULL AND automation_id IS NULL)"
    " OR (message_id IS NULL AND conversation_id IS NULL AND proposal_id IS NULL"
    " AND skill_proposal_id IS NULL AND space_id IS NULL AND automation_id IS NOT NULL)"
)

# `herd_message_system_only_in_threads()` as M6 left it (`10b0b021104e`), with a place
# for one more exception: a term's system entry, the root of the thread an
# automation's run answers in, may stand at the top level of the automation's
# channel (it names the term: `client_id` is the term's row in the log).
MESSAGE_PLACE = """
CREATE OR REPLACE FUNCTION herd_message_system_only_in_threads() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.kind = 'system' AND {replies} NOT EXISTS (
        SELECT 1 FROM conversation
        WHERE id = NEW.conversation_id AND kind IN ('thread_page', 'thread_ticket')
    ) AND NOT EXISTS (
        SELECT 1 FROM conversation_participant
        WHERE conversation_id = NEW.conversation_id AND principal_type = 'agent'
    ){automation} THEN
        RAISE EXCEPTION 'system_message_outside_thread' USING ERRCODE = 'check_violation';
    END IF;
    IF NEW.kind IN ('agent', 'approval', 'question') AND NOT EXISTS (
        SELECT 1 FROM conversation_participant
        WHERE conversation_id = NEW.conversation_id AND principal_type = 'agent'
          AND principal_id = NEW.author_id
    ) AND NOT EXISTS (
        SELECT 1 FROM conversation c
        JOIN space_member m ON m.space_id = c.space_id
        WHERE c.id = NEW.conversation_id
          AND c.kind IN ('channel', 'thread_page', 'thread_ticket')
          AND m.member_type = 'agent' AND m.member_id = NEW.author_id
    ) THEN
        RAISE EXCEPTION 'agent_message_outside_its_places' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END
$$
"""
TERM_ENTRY = """ AND NOT EXISTS (
        SELECT 1 FROM automation_firing f JOIN automation a ON a.id = f.automation_id
        WHERE f.id = NEW.client_id AND a.conversation_id = NEW.conversation_id
    )"""


def _replace_check(table: str, name: str, condition: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, condition)


def upgrade() -> None:
    op.execute(
        sa.text(MESSAGE_PLACE.format(replies="NEW.parent_id IS NULL AND", automation=TERM_ENTRY))
    )
    op.add_column(
        "automation",
        sa.Column("failures", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint(op.f("ck_automation_failures"), "automation", "failures >= 0")
    _replace_check(
        "automation",
        "paused_reason",
        PAUSED.format("paused_reason IN ('manual', 'owner', 'failing')"),
    )
    _replace_check(
        "automation_firing",
        "outcome",
        f"outcome IN ({OUTCOMES}, 'skipped_budget', 'skipped_policy')",
    )
    op.add_column("automation_firing", sa.Column("instruction", sa.Text(), nullable=True))
    op.create_check_constraint(
        op.f("ck_automation_firing_instruction"),
        "automation_firing",
        "(outcome = 'started') = (instruction IS NOT NULL)",
    )
    op.add_column("notification", sa.Column("automation_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_notification_automation_id_automation"),
        "notification",
        "automation",
        ["automation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_notification_automation_id", "notification", ["automation_id"])
    _replace_check("notification", "target", WIDER_TARGET)
    _replace_check("notification", "reason", f"reason IN ({NOTIFY}, 'automation')")


def downgrade() -> None:
    op.execute(
        "DELETE FROM message m USING conversation c WHERE c.id = m.conversation_id"
        " AND c.kind = 'channel' AND m.kind = 'system' AND m.parent_id IS NULL"
    )
    op.execute(sa.text(MESSAGE_PLACE.format(replies="NEW.parent_id IS NULL AND", automation="")))
    op.execute("DELETE FROM notification WHERE automation_id IS NOT NULL")
    _replace_check("notification", "reason", f"reason IN ({NOTIFY})")
    _replace_check("notification", "target", TARGET)
    op.drop_index("ix_notification_automation_id", table_name="notification")
    op.drop_constraint(
        op.f("fk_notification_automation_id_automation"), "notification", type_="foreignkey"
    )
    op.drop_column("notification", "automation_id")
    op.drop_constraint(op.f("ck_automation_firing_instruction"), "automation_firing", type_="check")
    op.drop_column("automation_firing", "instruction")
    op.execute(
        "UPDATE automation_firing SET outcome = 'skipped_paused_agent'"
        " WHERE outcome IN ('skipped_budget', 'skipped_policy')"
    )
    _replace_check("automation_firing", "outcome", f"outcome IN ({OUTCOMES})")
    op.execute(
        "UPDATE automation SET paused_reason = 'manual' WHERE paused_reason IN ('owner', 'failing')"
    )
    _replace_check("automation", "paused_reason", PAUSED.format("paused_reason IN ('manual')"))
    op.drop_constraint(op.f("ck_automation_failures"), "automation", type_="check")
    op.drop_column("automation", "failures")

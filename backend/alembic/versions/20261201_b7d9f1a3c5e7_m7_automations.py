"""m7 automations (plan M7 task 2): the tables `automation` and `automation_firing`
(the log, unique per term), and a run's link to the automation that fired it.

- `run.automation_id` (nullable, cascading with its automation) and the check that
  every run has a cause admits it as a third cause beside a message and a ticket.
- `run.lane_id` loses its foreign key to `message`: an automation's run has the
  automation as its lane (one open run per automation), which is no message.
  Messages are never deleted one by one (they are marked deleted), and a
  conversation's deletion still takes its runs with it (`run.conversation_id`).

Expand-only: new tables and a nullable column; the check is widened and a foreign
key dropped, so the previous release reads and writes runs as before. A pod of the
previous release that claims an automation's run cannot answer it (it knows no such
cause) and ends it with an error after its attempts; automations are made only by
code of this release.

Revision ID: b7d9f1a3c5e7
Revises: a1c3e5f7b9d2
Create Date: 2026-11-14 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d9f1a3c5e7"
down_revision: str | None = "a1c3e5f7b9d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TRIGGER_BEFORE = "trigger_message_id IS NOT NULL OR work_item_id IS NOT NULL"
TRIGGER_AFTER = TRIGGER_BEFORE + " OR automation_id IS NOT NULL"


def upgrade() -> None:
    op.create_table(
        "automation",
        sa.Column("owner_user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("cron", sa.String(length=120), nullable=True),
        sa.Column("time_zone", sa.String(length=64), nullable=True),
        sa.Column("next_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("paused_reason", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint("kind IN ('once', 'recurring')", name=op.f("ck_automation_kind")),
        sa.CheckConstraint(
            "state IN ('active', 'paused', 'done')", name=op.f("ck_automation_state")
        ),
        sa.CheckConstraint(
            "(state = 'paused') = (paused_reason IS NOT NULL) AND "
            "(paused_reason IS NULL OR paused_reason IN ('manual'))",
            name=op.f("ck_automation_paused_reason"),
        ),
        sa.CheckConstraint(
            "(kind = 'recurring') = (cron IS NOT NULL)", name=op.f("ck_automation_cron")
        ),
        sa.CheckConstraint(
            "cron IS NULL OR time_zone IS NOT NULL", name=op.f("ck_automation_cron_zone")
        ),
        sa.CheckConstraint(
            "kind <> 'once' OR time_zone IS NULL", name=op.f("ck_automation_once_zone")
        ),
        sa.CheckConstraint(
            "(state = 'done') = (next_due_at IS NULL)", name=op.f("ck_automation_next_due")
        ),
        sa.CheckConstraint("state <> 'done' OR kind = 'once'", name=op.f("ck_automation_done")),
        sa.CheckConstraint(
            "char_length(instruction) BETWEEN 1 AND 4000", name=op.f("ck_automation_instruction")
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agent.id"],
            name=op.f("fk_automation_agent_id_agent"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversation.id"],
            name=op.f("fk_automation_conversation_id_conversation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_automation_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["owner_user_id"], ["app_user.id"], name=op.f("fk_automation_owner_user_id_app_user")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation")),
    )
    op.create_index(
        "ix_automation_due",
        "automation",
        ["next_due_at"],
        postgresql_where=sa.text("state = 'active'"),
    )
    op.create_index("ix_automation_owner_user_id", "automation", ["owner_user_id"])
    op.create_index("ix_automation_agent_id", "automation", ["agent_id"])
    op.create_index("ix_automation_conversation_id", "automation", ["conversation_id"])
    op.create_index(op.f("ix_automation_org_id"), "automation", ["org_id"])

    op.add_column("run", sa.Column("automation_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_run_automation_id_automation"),
        "run",
        "automation",
        ["automation_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_run_automation_id", "run", ["automation_id"])
    op.drop_constraint(op.f("ck_run_trigger"), "run", type_="check")
    op.create_check_constraint(op.f("ck_run_trigger"), "run", TRIGGER_AFTER)
    op.drop_constraint(op.f("fk_run_lane_id_message"), "run", type_="foreignkey")

    op.create_table(
        "automation_firing",
        sa.Column("automation_id", sa.UUID(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('started', 'skipped_busy', 'skipped_paused_agent')",
            name=op.f("ck_automation_firing_outcome"),
        ),
        sa.CheckConstraint(
            "run_id IS NULL OR outcome = 'started'", name=op.f("ck_automation_firing_run")
        ),
        sa.ForeignKeyConstraint(
            ["automation_id"],
            ["automation.id"],
            name=op.f("fk_automation_firing_automation_id_automation"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_automation_firing_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["run.id"],
            name=op.f("fk_automation_firing_run_id_run"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_automation_firing")),
    )
    op.create_index(
        "uq_automation_firing_term", "automation_firing", ["automation_id", "due_at"], unique=True
    )
    op.create_index("ix_automation_firing_run_id", "automation_firing", ["run_id"])
    op.create_index(op.f("ix_automation_firing_org_id"), "automation_firing", ["org_id"])


def downgrade() -> None:
    op.drop_table("automation_firing")
    # The lanes of automations' runs name no message: their runs go with the column.
    op.execute("DELETE FROM run WHERE automation_id IS NOT NULL")
    op.create_foreign_key(
        op.f("fk_run_lane_id_message"), "run", "message", ["lane_id"], ["id"], ondelete="CASCADE"
    )
    op.drop_constraint(op.f("ck_run_trigger"), "run", type_="check")
    op.create_check_constraint(op.f("ck_run_trigger"), "run", TRIGGER_BEFORE)
    op.drop_index("ix_run_automation_id", table_name="run")
    op.drop_constraint(op.f("fk_run_automation_id_automation"), "run", type_="foreignkey")
    op.drop_column("run", "automation_id")
    op.drop_table("automation")

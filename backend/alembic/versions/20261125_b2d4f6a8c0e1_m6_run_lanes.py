"""m6 run lanes (plan M6 task 9, ruling on open runs): "one open run" counts per lane,
not per conversation. `run.lane_id` is the root of the channel thread a mention's run
answers in; NULL for every other run, whose lane is its conversation (a DM, a page
thread, a ticket thread: one per ticket). So a run waiting for a release in one
thread of a channel holds that thread only.

The three unique indexes per conversation become indexes over the lane,
`COALESCE(lane_id, conversation_id)`: running and active (running or waiting) per
lane, queued per lane and agent (a handover's run waits queued behind the run that
handed the ticket over, which may itself be queued again after a release).

Rolling update: for every run the previous release writes (no lane) the running and
active indexes are the old ones, and its claim and start checks look at the
conversation in their own statements, so they stay correct. Its queueing names the
old queued index (`ON CONFLICT (conversation_id) WHERE state = 'queued'`), which no
longer finds an arbiter: a DM to an agent or a mention through a pod of the previous
release fails until that pod is replaced. There is no index that both serves that
clause and lets two threads of a channel queue a run each; nothing with these
indexes has been released yet (docs/KI.md, release notes).

Not expand-only, and an exception, not a pattern: this revision drops the per-
conversation unique indexes in the same step that adds the lane ones, so code of the
previous release on this schema could start two runs in one conversation (and fails
to queue, above). The house rule (CLAUDE.md: expand first, contract in a later
release) was set aside only because no release has run agents on the old indexes
(version 0.1.0, no tag): there is no previous release whose pods could meet this
schema. A later migration must keep the rule: add the new indexes here, drop the old
ones a release later.

Revision ID: b2d4f6a8c0e1
Revises: 10b0b021104e
Create Date: 2026-11-14 20:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2d4f6a8c0e1"
down_revision: str | None = "10b0b021104e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LANE = sa.text("COALESCE(lane_id, conversation_id)")
STATES = {
    "queued": "state = 'queued'",
    "running": "state = 'running'",
    "active": "state IN ('running', 'waiting')",
}


def upgrade() -> None:
    op.add_column("run", sa.Column("lane_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        op.f("fk_run_lane_id_message"), "run", "message", ["lane_id"], ["id"], ondelete="CASCADE"
    )
    for name, where in STATES.items():
        columns = [LANE, sa.text("agent_id")] if name == "queued" else [LANE]
        op.create_index(
            f"uq_run_{name}_per_lane", "run", columns, unique=True, postgresql_where=sa.text(where)
        )
        op.drop_index(
            f"uq_run_{name}_per_conversation", table_name="run", postgresql_where=sa.text(where)
        )


def downgrade() -> None:
    # Runs that are open at once in one conversation cannot stay open: those of channel
    # threads, and a second queued run (a handover behind a resumed run).
    op.execute(
        "UPDATE run SET state = 'done', stop_reason = 'cancelled', lease_until = NULL, "
        "wait_until = NULL, finished_at = now() WHERE state <> 'done' AND ("
        "lane_id IS NOT NULL OR (state = 'queued' AND EXISTS (SELECT 1 FROM run o "
        "WHERE o.conversation_id = run.conversation_id AND o.state = 'queued' "
        "AND o.lane_id IS NULL AND (o.created_at, o.id) < (run.created_at, run.id))))"
    )
    for name, where in STATES.items():
        op.create_index(
            f"uq_run_{name}_per_conversation",
            "run",
            ["conversation_id"],
            unique=True,
            postgresql_where=sa.text(where),
        )
        op.drop_index(f"uq_run_{name}_per_lane", table_name="run", postgresql_where=sa.text(where))
    op.drop_constraint(op.f("fk_run_lane_id_message"), "run", type_="foreignkey")
    op.drop_column("run", "lane_id")

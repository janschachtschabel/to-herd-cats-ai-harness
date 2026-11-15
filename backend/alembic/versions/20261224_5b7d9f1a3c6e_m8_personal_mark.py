"""m8 personal mark (module review M8 2, finding G1): the mark follows the content.

`message.personal` notes a message that a run wrote while it held what its asker read
through her own connector (only where she is alone with the agent); a run whose
history window holds one is marked from its start. `run_event.kind` may also be
`mark`: the journal fact that the history gave the run such content, written at its
start, so replay and every take-up keep the mark.

Expand only: a column with a constant default (no rewrite) and a wider check (added
`NOT VALID` and validated afterwards, so writes go on meanwhile). The previous release
neither reads nor writes either; its journal replay and run view pass over a `mark`
event it does not know.

Revision ID: 5b7d9f1a3c6e
Revises: a6ce005832fd
Create Date: 2026-11-24 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5b7d9f1a3c6e"
down_revision: str | None = "a6ce005832fd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = "kind IN ('model_call', 'tool_call', 'stop')"
NEW_KINDS = "kind IN ('model_call', 'tool_call', 'stop', 'mark')"


def _check(kinds: str) -> None:
    op.drop_constraint(op.f("ck_run_event_kind"), "run_event", type_="check")
    op.execute(f"ALTER TABLE run_event ADD CONSTRAINT ck_run_event_kind CHECK ({kinds}) NOT VALID")
    op.execute("ALTER TABLE run_event VALIDATE CONSTRAINT ck_run_event_kind")


def upgrade() -> None:
    op.add_column(
        "message",
        sa.Column("personal", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    _check(NEW_KINDS)


def downgrade() -> None:
    op.execute("DELETE FROM run_event WHERE kind = 'mark'")
    _check(OLD_KINDS)
    op.drop_column("message", "personal")

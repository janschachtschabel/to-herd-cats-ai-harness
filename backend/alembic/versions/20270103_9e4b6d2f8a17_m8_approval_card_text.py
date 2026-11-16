"""m8 approval card text (module review M8 5, L1): an approval card in a conversation
says only its tool's name; its summary is the asked person's alone. A card written
before that carries its old summary as its text, which could name a string the model
chose: every approval card gets its approval's tool as its text, as new cards do.

Data only, idempotent (a card whose text is its tool already is left alone; the
search column follows by itself). Expand-safe: the previous release reads a card's
text without parsing it, and its new cards still carry the summary until it is
rolled out. Nothing to undo: the old texts are not kept.

Revision ID: 9e4b6d2f8a17
Revises: 7c2e9a4f1b86
Create Date: 2027-01-03 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "9e4b6d2f8a17"
down_revision: str | None = "7c2e9a4f1b86"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE message SET body_md = approval.tool"
        " FROM approval"
        " WHERE message.kind = 'approval'"
        " AND message.org_id = approval.org_id"
        " AND message.client_id = approval.id"
        " AND message.body_md IS DISTINCT FROM approval.tool"
    )


def downgrade() -> None:
    pass  # the old texts are gone, by design

"""m8 external tool names (module review M8 1, finding 1): an external tool's run name
is `ext_<the tool's whole id, 32 hex>_<its name>` (it was `ext_<12 hex>_<name>`, and
the first 12 hex of a UUIDv7 are only its millisecond, so two tools of one listing
could share a name).

Expand only, data: every agent's entry under an old name that stands for exactly one
tool of its organisation gets a twin under the new name; the old rows stay, so the
previous release keeps reading them during a rollout, and the new code never matches
them (an agent's next change of its entries replaces them). An old name that stood
for two tools gets no twin: neither tool is granted by it any more, and the agent's
tool screen shows both without an entry.

Revision ID: f1afc79e3de4
Revises: b3e7c1d5f9a2
Create Date: 2026-11-20 09:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "f1afc79e3de4"
down_revision: str | None = "b3e7c1d5f9a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TWINS = """
        WITH named AS (
            SELECT t.org_id,
                   left('ext_' || left(replace(t.id::text, '-', ''), 12) || '_' || regexp_replace(t.name, '[^A-Za-z0-9_-]', '_', 'g'), 64)
                       AS old,
                   left('ext_' || replace(t.id::text, '-', '') || '_' || regexp_replace(t.name, '[^A-Za-z0-9_-]', '_', 'g'), 64) AS new
            FROM mcp_server_tool t
        ),
        single AS (
            SELECT org_id, old, min(new) AS new
            FROM named
            GROUP BY org_id, old
            HAVING count(*) = 1
        )
        INSERT INTO agent_tool (org_id, agent_id, tool, policy)
        SELECT a.org_id, a.agent_id, s.new, a.policy
        FROM agent_tool a
        JOIN single s ON s.org_id = a.org_id AND s.old = a.tool
        ON CONFLICT DO NOTHING
        """


def upgrade() -> None:
    op.execute(TWINS)


def downgrade() -> None:
    op.execute("DELETE FROM agent_tool WHERE tool ~ '^ext_[0-9a-f]{32}_'")

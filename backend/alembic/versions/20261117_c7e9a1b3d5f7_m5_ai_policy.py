"""m5 ai policy: a space's AI policy (`space.ai_policy`, `space.allowed_locations`,
spec 7.3) and the no-AI lock of pages and attachments (`no_ai`, spec 11), with a
`version` for attachments (the lock is a write that can race).

Backward compatible: only new columns with server defaults; the previous release
neither reads nor writes them, and its inserts get the defaults.

Revision ID: c7e9a1b3d5f7
Revises: c6e8a0b2d4f6
Create Date: 2026-11-17 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c7e9a1b3d5f7"
down_revision: str | None = "c6e8a0b2d4f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "space",
        sa.Column("ai_policy", sa.String(length=16), server_default="any", nullable=False),
    )
    op.add_column(
        "space",
        sa.Column(
            "allowed_locations",
            postgresql.ARRAY(sa.String(length=16)),
            server_default=sa.text("'{}'::varchar[]"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        op.f("ck_space_ai_policy"), "space", "ai_policy IN ('any', 'restricted', 'none')"
    )
    op.create_check_constraint(
        op.f("ck_space_allowed_locations"),
        "space",
        "allowed_locations <@ ARRAY['local', 'eu', 'external']::varchar[] "
        "AND (ai_policy = 'restricted') = (cardinality(allowed_locations) > 0)",
    )
    op.add_column(
        "page", sa.Column("no_ai", sa.Boolean(), server_default=sa.false(), nullable=False)
    )
    op.add_column(
        "attachment",
        sa.Column("no_ai", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "attachment",
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("attachment", "version")
    op.drop_column("attachment", "no_ai")
    op.drop_column("page", "no_ai")
    op.drop_constraint(op.f("ck_space_allowed_locations"), "space", type_="check")
    op.drop_constraint(op.f("ck_space_ai_policy"), "space", type_="check")
    op.drop_column("space", "allowed_locations")
    op.drop_column("space", "ai_policy")

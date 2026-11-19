"""m9 session device (plan M9 task 18, J8, ASVS 5.0 V7.5.2): a person lists her own
login sessions, each with the time it opened and a device hint (browser and system,
no version).

Expand only: two new columns, one with a server default. The previous release (1.0.0)
never names them; its sessions get the time of their insert and no hint.

Revision ID: f2a5b8c3d6e9
Revises: e1f4a7c2b9d3
Create Date: 2027-01-09 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a5b8c3d6e9"
down_revision: str | None = "e1f4a7c2b9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_session",
        sa.Column(
            "signed_in_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.add_column("user_session", sa.Column("device", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("user_session", "device")
    op.drop_column("user_session", "signed_in_at")

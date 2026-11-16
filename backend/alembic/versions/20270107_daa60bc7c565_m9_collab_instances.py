"""m9 collab instances (plan M9 task 15, decision 17): several collab processes announce
themselves (`collab_instance`, infrastructure without `org_id`, an explicit decision of
the plan), and each page is bound to one of them (`collab_page_owner`, with `epoch`).

Expand only: two new tables. The previous release (1.0.0) neither reads nor writes
them; its collab process names no instance, which the API serves as before while no
instance owns the page.

Revision ID: daa60bc7c565
Revises: c4d8e1f7a2b9
Create Date: 2027-01-07 09:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "daa60bc7c565"
down_revision: str | None = "c4d8e1f7a2b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "collab_instance",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("url", sa.String(length=256), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("draining", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_collab_instance")),
    )
    op.create_index(
        op.f("ix_collab_instance_heartbeat_at"), "collab_instance", ["heartbeat_at"], unique=False
    )
    op.create_table(
        "collab_page_owner",
        sa.Column("page_id", sa.UUID(), nullable=False),
        sa.Column("instance_id", sa.UUID(), nullable=True),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instance_id"],
            ["collab_instance.id"],
            name=op.f("fk_collab_page_owner_instance_id_collab_instance"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_collab_page_owner_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["page_id"],
            ["page.id"],
            name=op.f("fk_collab_page_owner_page_id_page"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("page_id", name=op.f("pk_collab_page_owner")),
    )
    op.create_index(
        op.f("ix_collab_page_owner_instance_id"),
        "collab_page_owner",
        ["instance_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_collab_page_owner_org_id"), "collab_page_owner", ["org_id"], unique=False
    )


def downgrade() -> None:
    op.drop_table("collab_page_owner")
    op.drop_table("collab_instance")

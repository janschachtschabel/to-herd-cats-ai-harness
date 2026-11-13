"""m3 conversations: channels, and `#allgemein` in the general space of every
installation that has one (new installations get it at bootstrap).

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5f7b9d1
Create Date: 2026-11-13 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision: str = "b2d4f6a8c0e2"
down_revision: str | None = "a1c3e5f7b9d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "conversation",
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("space_id", sa.UUID(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=True),
        sa.Column("topic", sa.String(length=250), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_type", sa.String(length=16), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "kind <> 'channel' OR (space_id IS NOT NULL AND name IS NOT NULL)",
            name=op.f("ck_conversation_channel_fields"),
        ),
        sa.CheckConstraint("kind IN ('channel')", name=op.f("ck_conversation_kind")),
        sa.CheckConstraint(
            "(created_by_type IS NULL) = (created_by_id IS NULL)",
            name=op.f("ck_conversation_created_by_pair"),
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organization.id"],
            name=op.f("fk_conversation_org_id_organization"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["space.id"],
            name=op.f("fk_conversation_space_id_space"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversation")),
    )
    op.create_index(op.f("ix_conversation_org_id"), "conversation", ["org_id"], unique=False)
    op.create_index("ix_conversation_space_id", "conversation", ["space_id"], unique=False)
    op.create_index(
        "uq_conversation_channel_name",
        "conversation",
        ["space_id", sa.literal_column("lower(name)").label("name_lower")],
        unique=True,
        postgresql_where=sa.text("kind = 'channel'"),
    )
    op.execute(sa.text(GENERAL_CHANNELS_SQL))


# A UUIDv7 in SQL (Postgres 16 has none built in): the time in ms over the first 48
# bits of a random UUID, version nibble 7. Ids are UUIDv7 everywhere (ordered by time).
_UUID7 = (
    "encode(set_bit(set_bit(overlay(uuid_send(gen_random_uuid()) placing"
    " substring(int8send(floor(extract(epoch FROM clock_timestamp()) * 1000)::bigint)"
    " FROM 3) FROM 1 FOR 6), 52, 1), 53, 1), 'hex')::uuid"
)

# `#allgemein` in each organisation's oldest open space named „Allgemein“ (the one
# bootstrap made), unless that space has a channel of that name already. One
# statement, so `alembic upgrade --sql` renders it too.
GENERAL_CHANNELS_SQL = f"""
INSERT INTO conversation (id, org_id, kind, space_id, name, created_at, version)
SELECT {_UUID7}, general.org_id, 'channel', general.id, 'allgemein', now(), 1
FROM (
    SELECT DISTINCT ON (s.org_id) s.id, s.org_id FROM space s
    WHERE s.kind = 'open' AND s.name = 'Allgemein'
    ORDER BY s.org_id, s.id
) AS general
WHERE NOT EXISTS (
    SELECT 1 FROM conversation c
    WHERE c.space_id = general.id AND c.kind = 'channel' AND lower(c.name) = 'allgemein'
)
"""  # noqa: S608 -- built from constants only


def add_general_channels(connection: Connection) -> None:
    connection.execute(sa.text(GENERAL_CHANNELS_SQL))


def downgrade() -> None:
    op.drop_index(
        "uq_conversation_channel_name",
        table_name="conversation",
        postgresql_where=sa.text("kind = 'channel'"),
    )
    op.drop_index("ix_conversation_space_id", table_name="conversation")
    op.drop_index(op.f("ix_conversation_org_id"), table_name="conversation")
    op.drop_table("conversation")

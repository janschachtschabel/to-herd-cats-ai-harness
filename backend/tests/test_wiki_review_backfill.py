"""The migration of page review (plan M7 task 6) gives every published page its
publication time as its last review, and drafts none: run on rows written before it,
inside a transaction that is rolled back afterwards."""

import uuid
from datetime import UTC, datetime

from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.migrations import alembic_config

BEFORE = "f2a4c6e8b0d1"
REVISION = "d4f6b8a0c2e4"
PUBLISHED = datetime(2025, 3, 4, 5, 6, tzinfo=UTC)
CREATED = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)


def _migrate(connection: Connection) -> dict[str, tuple[datetime | None, datetime | None]]:
    config = alembic_config()
    config.attributes["connection"] = connection
    command.downgrade(config, BEFORE)
    org, space, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    connection.execute(text("INSERT INTO organization (id, name) VALUES (:id, 'Alt')"), {"id": org})
    connection.execute(
        text(
            "INSERT INTO space (id, org_id, kind, name, version)"
            " VALUES (:id, :org, 'team', 'Alt', 1)"
        ),
        {"id": space, "org": org},
    )
    for slug, status, published in (
        ("veroeffentlicht", "published", PUBLISHED),
        ("ohne-zeit", "published", None),
        ("entwurf", "draft", None),
    ):
        connection.execute(
            text(
                "INSERT INTO page (id, org_id, space_id, title, slug, path, sort_order,"
                " content_md, status, version, collab_generation, created_by_type,"
                " created_by_id, updated_by_type, updated_by_id, published_at,"
                " created_at, updated_at)"
                " VALUES (:id, :org, :space, :title, :slug, :path, 0, '', :status, 1, 0,"
                " 'user', :user, 'user', :user, :published, :created, :created)"
            ),
            {
                "id": uuid.uuid4(),
                "org": org,
                "space": space,
                "title": slug,
                "slug": slug,
                "path": slug,
                "status": status,
                "user": user,
                "published": published,
                "created": CREATED,
            },
        )
    command.upgrade(config, REVISION)
    rows = connection.execute(
        text("SELECT slug, reviewed_at, review_notified_at FROM page WHERE org_id = :org"),
        {"org": org},
    ).all()
    command.upgrade(config, "head")
    return {slug: (reviewed, notified) for slug, reviewed, notified in rows}


async def test_published_pages_count_as_reviewed_when_published(engine: AsyncEngine) -> None:
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            found = await connection.run_sync(_migrate)
        finally:
            await transaction.rollback()
    assert found == {
        "veroeffentlicht": (PUBLISHED, None),
        "ohne-zeit": (CREATED, None),
        "entwurf": (None, None),
    }

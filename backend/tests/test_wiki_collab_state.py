"""The live state table keeps only what code reads (rule 5, review M2 R15)."""

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wiki.collab_models import PageCollabState


async def test_collab_state_has_only_read_columns(session: AsyncSession) -> None:
    expected = {"page_id", "org_id", "generation", "ydoc"}
    assert {c.name for c in PageCollabState.__table__.columns} == expected

    def columns(connection: object) -> set[str]:
        return {c["name"] for c in inspect(connection).get_columns("page_collab_state")}

    connection = await session.connection()
    assert await connection.run_sync(columns) == expected  # the migrated table too

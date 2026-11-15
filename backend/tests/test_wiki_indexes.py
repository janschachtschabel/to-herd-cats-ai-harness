"""The indexes the wiki's own queries need (review M2 R19): the foreign key of a
page's parent (a purge checks it once per deleted row) and the search's title prefix
(every keystroke in the palette). The planner must be able to use them."""

from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.modules.search.repository import title_starts_with
from app.modules.wiki.models import Page


async def _plan(session: AsyncSession, stmt: object) -> str:
    sql = stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})  # type: ignore[attr-defined]
    await session.execute(text("SET LOCAL enable_seqscan = off"))
    rows = (await session.execute(text(f"EXPLAIN {sql}"))).scalars().all()
    return "\n".join(rows)


async def test_a_parent_is_found_without_scanning_the_pages(session: AsyncSession) -> None:
    plan = await _plan(session, select(Page.id).where(Page.parent_id == uuid7()))
    assert "ix_page_parent_id" in plan, plan


async def test_a_title_prefix_is_found_by_index(session: AsyncSession) -> None:
    plan = await _plan(session, select(Page.id).where(title_starts_with("Urlau_b%")))
    assert "ix_page_title_prefix" in plan, plan

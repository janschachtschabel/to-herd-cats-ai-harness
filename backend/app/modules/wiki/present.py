"""Pages as the API shows them: with the ids of their tags, read for a whole list in
one query."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.actor import Actor
from app.modules.tags.models import SubjectType
from app.modules.tags.service import TagService
from app.modules.wiki.models import Page
from app.modules.wiki.schemas import PageOut, TreeNodeOut


async def page_out(session: AsyncSession, actor: Actor, page: Page) -> PageOut:
    tags = await TagService(session).tags_for(actor, SubjectType.PAGE, [page.id])
    return PageOut.of(page, tags=[t.id for t in tags.get(page.id, [])])


async def tree_out(
    session: AsyncSession, actor: Actor, page: pagination.Page[Page]
) -> pagination.Page[TreeNodeOut]:
    tags = await TagService(session).tags_for(actor, SubjectType.PAGE, [p.id for p in page.items])
    return pagination.Page[TreeNodeOut](
        items=[TreeNodeOut.of(p, tags=[t.id for t in tags.get(p.id, [])]) for p in page.items],
        next_cursor=page.next_cursor,
    )

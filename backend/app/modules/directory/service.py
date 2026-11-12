"""The directory: the people and groups of the organisation, by name, so that space
admins without `user.manage` or `group.manage` can add members. Needs `directory.read`
(everyone but guests); shows only active people."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.pagination import Page, decode_key_cursor, encode_key_cursor
from app.core.principal import PrincipalType
from app.modules.directory.repository import DirectoryEntry, DirectoryRepository
from app.modules.directory.schemas import DirectoryQuery

ALL_TYPES = frozenset({PrincipalType.USER, PrincipalType.GROUP})


class DirectoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.directory = DirectoryRepository(session)

    async def search(self, actor: Actor, query: DirectoryQuery) -> Page[DirectoryEntry]:
        await require(self.session, actor, Action.DIRECTORY_READ)
        after = decode_key_cursor(query.cursor) if query.cursor else None
        types = frozenset({query.type}) if query.type else ALL_TYPES
        rows = await self.directory.search(
            actor.org_id, query.q.strip(), types, after, query.limit + 1
        )
        items = rows[: query.limit]
        more = len(rows) > query.limit
        cursor = encode_key_cursor(items[-1].key, items[-1].id) if more else None
        return Page[DirectoryEntry](items=items, next_cursor=cursor)

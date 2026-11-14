"""The directory: the people and groups of the organisation, by name, so that space
admins without `user.manage` or `group.manage` can add members. Needs `directory.read`
(everyone but guests); shows only active people. With a space, only the people who may
read it (and the caller must read it too: otherwise 404, as for an unknown space).
Agents (not drafts) appear only for people with `ai.use` (plan M5: whoever has no AI
sees no agent), and never with a space; a personal agent only for its owner (plan M6),
admins included."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require
from app.core.pagination import Page, decode_key_cursor, encode_key_cursor
from app.core.principal import PrincipalType
from app.modules.directory.repository import DirectoryEntry, DirectoryRepository
from app.modules.directory.schemas import DirectoryQuery

ALL_TYPES = frozenset({PrincipalType.USER, PrincipalType.GROUP, PrincipalType.AGENT})


class DirectoryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.directory = DirectoryRepository(session)

    async def search(self, actor: Actor, query: DirectoryQuery) -> Page[DirectoryEntry]:
        await require(self.session, actor, Action.DIRECTORY_READ)
        if query.space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, query.space_id)
        after = decode_key_cursor(query.cursor) if query.cursor else None
        types = frozenset({query.type}) if query.type else ALL_TYPES
        if query.space_id is not None:
            types = types & {PrincipalType.USER}
        if PrincipalType.AGENT in types and not await can(self.session, actor, Action.AI_USE):
            types = types - {PrincipalType.AGENT}
        rows = await self.directory.search(
            actor.org_id,
            query.q.strip(),
            types,
            after,
            query.limit + 1,
            query.space_id,
            viewer=actor.principal.id,
        )
        items = rows[: query.limit]
        more = len(rows) > query.limit
        cursor = encode_key_cursor(items[-1].key, items[-1].id) if more else None
        return Page[DirectoryEntry](items=items, next_cursor=cursor)

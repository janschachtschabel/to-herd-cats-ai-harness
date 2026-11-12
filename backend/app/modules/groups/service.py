"""Groups: create, rename, delete, and their members (people in M1).

Changes to one organisation's groups are serialised (`lock_writes`), so the name and
version checks hold under concurrent requests. Every method needs `group.manage`;
every change is audited in its transaction.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.errors import Conflict, NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import Principal
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.groups.models import Group, GroupMember
from app.modules.groups.repository import GroupRepository
from app.modules.groups.schemas import GroupCreate, GroupUpdate
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.repository import UserRepository


class GroupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.groups = GroupRepository(session)
        self.users = UserRepository(session)

    async def create(self, actor: Actor, data: GroupCreate) -> Group:
        await require(self.session, actor, Action.GROUP_MANAGE)
        await self.groups.lock_writes(actor.org_id)
        await self._ensure_name_free(actor.org_id, data.name)
        group = await self.groups.add(
            Group(org_id=actor.org_id, name=data.name, description=data.description)
        )
        await self._audit(actor, "group.created", group, {"name": group.name})
        return group

    async def get(self, actor: Actor, group_id: uuid.UUID) -> Group:
        await require(self.session, actor, Action.GROUP_MANAGE)
        return _found(await self.groups.get(actor.org_id, group_id))

    async def update(
        self, actor: Actor, group_id: uuid.UUID, data: GroupUpdate, version: int
    ) -> Group:
        await require(self.session, actor, Action.GROUP_MANAGE)
        group = await self._current(actor, group_id)
        if group.version != version:
            raise Conflict(code="groups.version_conflict")
        before = snapshot(group, ("name", "description"))
        if data.name is not None and data.name != group.name:
            await self._ensure_name_free(actor.org_id, data.name)
            group.name = data.name
        if "description" in data.model_fields_set:
            group.description = data.description
        group.version += 1
        await self.session.flush()
        if changed := changes(before, group):
            await self._audit(actor, "group.updated", group, {"changes": changed})
        return group

    async def delete(self, actor: Actor, group_id: uuid.UUID) -> None:
        """Its memberships go with it: the database cascades `group_member`; its space
        memberships (no foreign key: `member_id` is polymorphic) are deleted here."""
        await require(self.session, actor, Action.GROUP_MANAGE)
        group = await self._current(actor, group_id)
        await SpaceRepository(self.session).delete_memberships_of(Principal.group(group.id))
        details = {"name": group.name}
        await self.groups.delete(group)
        await self._audit(actor, "group.deleted", group, details)

    async def list(self, actor: Actor, params: PageParams) -> Page[Group]:
        await require(self.session, actor, Action.GROUP_MANAGE)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.groups.page(actor.org_id, after, params.limit + 1)
        return id_page(rows, params.limit, lambda g: g.id)

    async def members(
        self, actor: Actor, group_id: uuid.UUID, params: PageParams
    ) -> Page[GroupMember]:
        group = await self.get(actor, group_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.groups.member_page(group.id, after, params.limit + 1)
        return id_page(rows, params.limit, lambda m: m.member_id)

    async def add_member(self, actor: Actor, group_id: uuid.UUID, principal: Principal) -> None:
        """Idempotent. The person must belong to the organisation."""
        group = await self.get(actor, group_id)
        if await self.users.get(actor.org_id, principal.id) is None:
            raise NotFound(code="users.not_found")
        if await self.groups.add_member(group.id, principal):
            await self._audit(actor, "group.member_added", group, _member(principal))

    async def remove_member(self, actor: Actor, group_id: uuid.UUID, principal: Principal) -> None:
        group = await self.get(actor, group_id)
        if not await self.groups.remove_member(group.id, principal):
            raise NotFound(code="groups.member_not_found")
        await self._audit(actor, "group.member_removed", group, _member(principal))

    async def _audit(
        self, actor: Actor, action: str, group: Group, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "group", group.id, details)

    async def _current(self, actor: Actor, group_id: uuid.UUID) -> Group:
        """The group as committed now, with the organisation's group writes locked."""
        await self.groups.lock_writes(actor.org_id)
        return _found(await self.groups.get_current(actor.org_id, group_id))

    async def _ensure_name_free(self, org_id: uuid.UUID, name: str) -> None:
        if await self.groups.get_by_name(org_id, name) is not None:
            raise Conflict(code="groups.name_taken")


def _member(principal: Principal) -> dict[str, Any]:
    return {"member_type": principal.type, "member_id": str(principal.id)}


def _found(group: Group | None) -> Group:
    if group is None:
        raise NotFound(code="groups.not_found")
    return group

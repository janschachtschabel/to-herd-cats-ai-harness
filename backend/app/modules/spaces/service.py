"""Spaces and their members.

Kinds: `open` and `team` are created through the API by anyone with `space.create`, who
becomes the space's admin; `personal` is created only here, once per person, with that
person as its one fixed member. Agents (M5) become members like people; only someone
who may see agents (`ai.use` or `agent.manage`) adds them or sees them in the member
list. Names need not be unique; URLs use ids. Changes made
by someone are audited in their transaction, and a membership change is announced to the
people concerned (`access.changed`); the personal space of a new person and the general
space of a new installation come with `user.created` and bootstrap.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, my_roles, require, visible_space_ids
from app.core.access_events import access_changed
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.permissions import SpaceRole
from app.core.principal import Principal, PrincipalType
from app.modules.agents.models import AgentStatus
from app.modules.agents.repository import AgentRepository
from app.modules.agents.standing import owned_by
from app.modules.audit.recorder import changes, record, snapshot
from app.modules.groups.repository import GroupRepository
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import NamedMember, SpaceRepository
from app.modules.spaces.schemas import SpaceUpdate
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

GENERAL_SPACE_NAME = "Allgemein"


class SpaceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.spaces = SpaceRepository(session)
        self.users = UserRepository(session)
        self.groups = GroupRepository(session)

    async def create(
        self,
        actor: Actor,
        kind: SpaceKind,
        name: str,
        description: str | None = None,
        icon: str | None = None,
    ) -> Space:
        if kind == SpaceKind.PERSONAL:
            raise ValidationFailed(code="spaces.kind_not_allowed")
        await require(self.session, actor, Action.SPACE_CREATE)
        space = await self._insert(actor.org_id, kind, name, description=description, icon=icon)
        await self.spaces.set_member(space.id, actor.principal, SpaceRole.ADMIN)
        await self._audit(actor, "space.created", space.id, {"kind": kind, "name": name})
        return space

    async def create_personal(self, user: User) -> Space:
        """The person's own space; called in the transaction that creates the person."""
        space = await self._insert(user.org_id, SpaceKind.PERSONAL, user.name, owner=user.id)
        await self.spaces.set_member(space.id, Principal.user(user.id), SpaceRole.ADMIN)
        return space

    async def create_general(self, org_id: uuid.UUID) -> Space | None:
        """The open space every installation starts with (bootstrap), unless it exists;
        the space it created."""
        if await self.spaces.general_exists(org_id, GENERAL_SPACE_NAME):
            return None
        return await self._insert(org_id, SpaceKind.OPEN, GENERAL_SPACE_NAME)

    async def get(self, actor: Actor, space_id: uuid.UUID) -> Space:
        await require(self.session, actor, Action.SPACE_READ, space_id)
        return await self._space(actor.org_id, space_id)

    async def my_roles(
        self, actor: Actor, spaces: Sequence[Space]
    ) -> dict[uuid.UUID, SpaceRole | None]:
        """The caller's role in each of `spaces`, for display."""
        roles = await my_roles(self.session, actor, [s.id for s in spaces])
        return {s.id: roles.get(s.id) for s in spaces}

    async def list_visible(
        self,
        actor: Actor,
        params: PageParams,
        *,
        include_others_personal: bool = True,
        among: Select[uuid.UUID] | None = None,
    ) -> Page[Space]:
        """Every space the actor may read; without `include_others_personal`, other
        people's personal spaces (which admins may read) are left out; with `among`,
        only the spaces it selects."""
        after = decode_id_cursor(params.cursor) if params.cursor else None
        own = None if include_others_personal else actor.principal.id
        ids = visible_space_ids(actor)
        if among is not None:
            ids = ids.where(Space.id.in_(among))
        rows = await self.spaces.page_among(ids, after, params.limit + 1, personal_only_of=own)
        return id_page(rows, params.limit, lambda s: s.id)

    async def update(
        self, actor: Actor, space_id: uuid.UUID, data: SpaceUpdate, version: int
    ) -> Space:
        await require(self.session, actor, Action.SPACE_MANAGE, space_id)
        space = _found(await self.spaces.get_for_update(actor.org_id, space_id))
        if space.version != version:
            raise Conflict(code="spaces.version_conflict")
        fields = ("name", "description", "icon", "ai_policy", "allowed_locations")
        before = snapshot(space, (*fields, "agent_write_policy", "review_interval_days"))
        if data.name is not None:
            space.name = data.name
        if "description" in data.model_fields_set:
            space.description = data.description
        if "icon" in data.model_fields_set:
            space.icon = data.icon
        if data.ai_policy is not None:
            space.ai_policy = data.ai_policy
            space.allowed_locations = [str(loc) for loc in data.allowed_locations or ()]
        if data.agent_write_policy is not None:
            space.agent_write_policy = data.agent_write_policy
        interval = data.review_interval_days
        if (
            "review_interval_days" in data.model_fields_set
            and interval != before["review_interval_days"]
        ):
            space.review_interval_days = interval
            space.review_checked_on = None  # the daily pass looks again at its next round
        space.version += 1
        await self.session.flush()
        if changed := changes(before, space):
            await self._audit(actor, "space.updated", space.id, {"changes": changed})
        return space

    async def members(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> Page[NamedMember]:
        await require(self.session, actor, Action.SPACE_READ, space_id)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.spaces.member_page(
            space_id, after, params.limit + 1, with_agents=await self._sees_agents(actor)
        )
        return id_page(rows, params.limit, lambda row: row.member.member_id)

    async def set_member(
        self,
        actor: Actor,
        space_id: uuid.UUID,
        member_type: PrincipalType,
        member_id: uuid.UUID,
        role: SpaceRole,
    ) -> NamedMember:
        """Add a person, a group or an agent, or change their role."""
        await self._members_changeable(actor, space_id)
        principal = Principal(member_type, member_id)
        name = await self._name_of(actor, principal)
        member = await self.spaces.set_member(space_id, principal, role)
        await self._audit(actor, "space.member_set", space_id, {**_member(principal), "role": role})
        await self._access_changed(actor, space_id, principal)
        return NamedMember(member, name)

    async def remove_member(
        self, actor: Actor, space_id: uuid.UUID, member_type: PrincipalType, member_id: uuid.UUID
    ) -> None:
        await self._members_changeable(actor, space_id)
        principal = Principal(member_type, member_id)
        # Agents exist only for those who may see them: the same 404 as for no member.
        hidden = member_type == PrincipalType.AGENT and not await self._sees_agents(actor)
        if hidden or not await self.spaces.remove_member(space_id, principal):
            raise NotFound(code="spaces.member_not_found")
        await self._audit(actor, "space.member_removed", space_id, _member(principal))
        await self._access_changed(actor, space_id, principal)

    async def _access_changed(
        self, actor: Actor, space_id: uuid.UUID, principal: Principal
    ) -> None:
        """The person, or the group's people, may see more or less now (an agent's
        runs read its memberships afresh at every step)."""
        if principal.type == PrincipalType.AGENT:
            return
        if principal.type == PrincipalType.GROUP:
            people = await self.groups.user_ids(principal.id)
        else:
            people = [principal.id]
        await access_changed(self.session, actor, people, space_id=space_id)

    async def _audit(
        self, actor: Actor, action: str, space_id: uuid.UUID, details: dict[str, Any]
    ) -> None:
        await record(self.session, actor, action, "space", space_id, details)

    async def _space(self, org_id: uuid.UUID, space_id: uuid.UUID) -> Space:
        return _found(await self.spaces.get(org_id, space_id))

    async def _members_changeable(self, actor: Actor, space_id: uuid.UUID) -> None:
        await require(self.session, actor, Action.SPACE_MANAGE, space_id)
        space = await self._space(actor.org_id, space_id)
        if space.kind == SpaceKind.PERSONAL:
            raise Conflict(code="spaces.personal_members_fixed")

    async def _sees_agents(self, actor: Actor) -> bool:
        return await can(self.session, actor, Action.AI_USE) or await can(
            self.session, actor, Action.AGENT_MANAGE
        )

    async def _name_of(self, actor: Actor, principal: Principal) -> str:
        """The person's, group's or agent's name; 404 unless it exists in the
        organisation (an agent also for someone who may not see agents, a draft agent
        for someone without `agent.manage`)."""
        org_id = actor.org_id
        if principal.type == PrincipalType.USER:
            if (user := await self.users.get(org_id, principal.id)) is None:
                raise NotFound(code="users.not_found")
            return user.name
        if principal.type == PrincipalType.AGENT:
            agent = await AgentRepository(self.session, org_id).get(principal.id)
            if agent is None or not await self._sees_agents(actor):
                raise NotFound(code="agent.not_found")
            manages = await can(self.session, actor, Action.AGENT_MANAGE)
            draft = agent.status == AgentStatus.DRAFT
            if draft and not manages:
                raise NotFound(code="agent.not_found")  # a draft: as for `visible_agent`
            if agent.owner_user_id is not None:  # a personal agent stays at home
                if not (manages or owned_by(agent, actor)):
                    raise NotFound(code="agent.not_found")
                raise ValidationFailed(code="agent.personal_space_only")
            return agent.name
        # Under the groups lock: a deletion running now finishes first (and then the
        # group is gone), or waits until this membership is committed and deletes it.
        await self.groups.lock_writes(org_id)
        if (group := await self.groups.get_current(org_id, principal.id)) is None:
            raise NotFound(code="groups.not_found")
        return group.name

    async def _insert(
        self,
        org_id: uuid.UUID,
        kind: SpaceKind,
        name: str,
        *,
        description: str | None = None,
        icon: str | None = None,
        owner: uuid.UUID | None = None,
    ) -> Space:
        space = Space(
            org_id=org_id,
            kind=kind,
            name=name,
            description=description,
            icon=icon,
            owner_user_id=owner,
        )
        return await self.spaces.add(space)


def _member(principal: Principal) -> dict[str, Any]:
    return {"member_type": principal.type, "member_id": str(principal.id)}


def _found(space: Space | None) -> Space:
    if space is None:  # only if it went away after the permission check
        raise NotFound(code="space.not_found")
    return space

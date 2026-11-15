"""Who uses which connection (spec 7.2), set by holders of `ai.manage` (everyone else:
404). The standard, the ordered group list and the switch for personal agents share
one version (the organisation's row); a person's own assignment has its own. A target
must be a chat connection of the organisation and one of its models; while an
assignment uses a connection, the connection cannot be deleted (409
`ai.connection_in_use`): writes here lock the connection shared, its deletion locks it
exclusively. A change is announced
(`access.changed`) to whom it may concern, so their clients reload `ai.use` at once
(ruling M5 (c)): a person's own assignment to them, the group list to the people of
every group in the old or the new list, the standard to every active person.

Personal agents follow (review M6 2, finding 5): every change writes the owner's new
effective connection and model onto the owner's personal agents in the same
transaction (an owner left without AI keeps what was stored: the agent cannot run).
So the claim counts their runs against the connection they call, and a connection
nothing uses any more can be deleted. A run still resolves the owner's assignment
when it starts (`agents/standing.run_target`).
"""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor
from app.core.access_events import access_changed
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, encode_id_cursor
from app.core.principal import SystemRole
from app.modules.ai.access import require_ai
from app.modules.ai.assignment_repository import AssignmentRepository, Named
from app.modules.ai.assignment_schemas import MAX_GROUP_ASSIGNMENTS, GroupItemIn, TargetIn
from app.modules.ai.effective import CHAT_PURPOSES, Effective, effective_assignment
from app.modules.ai.models import GroupAssignment, OrgAssignment, UserAssignment
from app.modules.ai.repository import ConnectionRepository
from app.modules.audit.recorder import record
from app.modules.groups.repository import GroupRepository
from app.modules.users.repository import UserRepository


class AssignmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> AssignmentRepository:
        return AssignmentRepository(self.session, actor.org_id)

    async def overview(self, actor: Actor) -> tuple[OrgAssignment | None, str | None]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        return await self.repo(actor).org()

    async def set_default(self, actor: Actor, target: TargetIn | None, version: int) -> None:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        org = await self._org(actor, version)
        if target is not None:
            await self._usable_target(actor, target)
        org.connection_id = target.connection_id if target else None
        org.model = target.model if target else None
        org.version += 1
        await self.session.flush()
        details = _target_details(target)
        await record(
            self.session, actor, "ai_assignment.default_set", "organization", actor.org_id, details
        )
        await self._follow(actor, None)
        everyone = await UserRepository(self.session).active_ids(actor.org_id)
        await access_changed(self.session, actor, everyone, space_id=None)

    async def set_personal_agents(self, actor: Actor, enabled: bool, version: int) -> None:
        """The switch for personal agents (plan M6 decision 13); everyone's
        `agent.create_personal` may change, so every active person is told."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        org = await self._org(actor, version)
        org.personal_agents = enabled
        org.version += 1
        await self.session.flush()
        await record(
            self.session,
            actor,
            "ai_assignment.personal_agents_set",
            "organization",
            actor.org_id,
            {"enabled": enabled},
        )
        everyone = await UserRepository(self.session).active_ids(actor.org_id)
        await access_changed(self.session, actor, everyone, space_id=None)

    async def groups(self, actor: Actor, params: PageParams) -> Page[Named[GroupAssignment]]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        after = _decode_position(params.cursor) if params.cursor else None
        rows = await self.repo(actor).group_page(after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = _encode_position(items[-1].row.position) if more else None
        return Page[Named[GroupAssignment]](items=items, next_cursor=cursor)

    async def set_groups(self, actor: Actor, items: Sequence[GroupItemIn], version: int) -> None:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        org = await self._org(actor, version)
        if len({i.group_id for i in items}) != len(items):
            raise ValidationFailed(code="ai.group_twice")
        groups = GroupRepository(self.session)
        # Under the groups lock: a group deleted now is gone first, or waits for this.
        await groups.lock_writes(actor.org_id)
        for item in items:
            if await groups.get_current(actor.org_id, item.group_id) is None:
                raise ValidationFailed(code="ai.group_not_found")
            await self._usable_target(actor, item)
        rows = [
            GroupAssignment(
                org_id=actor.org_id,
                group_id=item.group_id,
                position=index,
                connection_id=item.connection_id,
                model=item.model,
            )
            for index, item in enumerate(items)
        ]
        before = await self.repo(actor).group_ids()
        await self.repo(actor).replace_groups(rows)
        org.version += 1
        await self.session.flush()
        details = {"groups": [{"group_id": str(i.group_id), **_target_details(i)} for i in items]}
        await record(
            self.session, actor, "ai_assignment.groups_set", "organization", actor.org_id, details
        )
        people: list[uuid.UUID] = []
        for group_id in dict.fromkeys([*before, *(i.group_id for i in items)]):
            people += await groups.user_ids(group_id)
        await self._follow(actor, people)
        await access_changed(self.session, actor, people, space_id=None)

    async def users(self, actor: Actor, params: PageParams) -> Page[Named[UserAssignment]]:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).user_page(after, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_id_cursor(items[-1].row.user_id) if more else None
        return Page[Named[UserAssignment]](items=items, next_cursor=cursor)

    async def set_user(
        self,
        actor: Actor,
        user_id: uuid.UUID,
        target: TargetIn | None,
        version: int | None,
    ) -> Named[UserAssignment]:
        """`target` None: expressly no AI."""
        await require_ai(self.session, actor, Action.AI_MANAGE)
        user = await UserRepository(self.session).get(actor.org_id, user_id)
        if user is None:
            raise NotFound(code="users.not_found")
        if target is not None and user.system_role == SystemRole.GUEST:
            raise ValidationFailed(code="ai.guest_not_assignable")
        connection_name = await self._usable_target(actor, target) if target else None
        repo = self.repo(actor)
        await repo.lock_user(user_id)
        row = await repo.user(user_id)
        current = row.version if row else None
        if current != version:
            raise Conflict(
                code="ai.assignment_version_conflict", details={"current_version": current}
            )
        if row is None:
            row = await repo.add(UserAssignment(org_id=actor.org_id, user_id=user_id, no_ai=True))
        else:
            row.version += 1
        row.no_ai = target is None
        row.connection_id = target.connection_id if target else None
        row.model = target.model if target else None
        await self.session.flush()
        details = {"no_ai": row.no_ai, **_target_details(target)}
        await record(self.session, actor, "ai_assignment.user_set", "user", user_id, details)
        await self._follow(actor, [user_id])
        await access_changed(self.session, actor, [user_id], space_id=None)
        return Named(row, user.name, connection_name)

    async def remove_user(self, actor: Actor, user_id: uuid.UUID, version: int) -> None:
        await require_ai(self.session, actor, Action.AI_MANAGE)
        repo = self.repo(actor)
        row = await repo.user(user_id)
        if row is None:
            raise NotFound(code="ai.assignment_not_found")
        if row.version != version:
            raise Conflict(
                code="ai.assignment_version_conflict", details={"current_version": row.version}
            )
        await repo.delete(row)
        await record(self.session, actor, "ai_assignment.user_removed", "user", user_id, {})
        await self._follow(actor, [user_id])
        await access_changed(self.session, actor, [user_id], space_id=None)

    async def _follow(self, actor: Actor, owners: Sequence[uuid.UUID] | None) -> None:
        """The owners' (None: everyone's) personal agents take their owner's target."""
        targets: dict[uuid.UUID, Effective | None] = {}
        for agent in await self.repo(actor).personal_agents_of(owners):
            owner = agent.owner_user_id
            assert owner is not None
            if owner not in targets:
                targets[owner] = await effective_assignment(self.session, actor.org_id, owner)
            target = targets[owner]
            if target is None or (agent.connection_id, agent.model) == (
                target.connection_id,
                target.model,
            ):
                continue
            agent.connection_id, agent.model = target.connection_id, target.model
            agent.version += 1
        await self.session.flush()

    async def _org(self, actor: Actor, version: int) -> OrgAssignment:
        org = await self.repo(actor).lock_org()
        if org.version != version:
            raise Conflict(
                code="ai.assignment_version_conflict", details={"current_version": org.version}
            )
        return org

    async def _usable_target(self, actor: Actor, target: TargetIn | GroupItemIn) -> str:
        """The connection's name, if it is a chat connection of the organisation with
        that model; locked shared, so it cannot be deleted before this commits."""
        connection = await ConnectionRepository(self.session, actor.org_id).get_shared(
            target.connection_id
        )
        if connection is None:
            raise ValidationFailed(code="ai.connection_not_found")
        if connection.purpose not in CHAT_PURPOSES:
            raise ValidationFailed(code="ai.connection_not_chat")
        if target.model not in connection.models:
            raise ValidationFailed(code="ai.model_unknown")
        return connection.name


def _target_details(target: TargetIn | GroupItemIn | None) -> dict[str, str | None]:
    if target is None:
        return {"connection_id": None, "model": None}
    return {"connection_id": str(target.connection_id), "model": target.model}


def _encode_position(position: int) -> str:
    return encode_id_cursor(uuid.UUID(int=position))


def _decode_position(cursor: str) -> int:
    position = decode_id_cursor(cursor).int
    if position >= MAX_GROUP_ASSIGNMENTS:
        raise ValidationFailed("Invalid cursor", code="validation_failed")
    return position

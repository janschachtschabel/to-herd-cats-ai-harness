"""The management of automations (plan M7 decisions 12 and 14): making, reading,
listing and changing them, the preview of terms, the log. Pausing, resuming,
deleting, running now and taking over: `control.py`.

Who sees one is `sight.py` (its owner, its agent's responsible person, the managers
of its place's space, `agent.manage`; nobody without `ai.use` or `agent.manage`):
anyone else gets 404 `automation.not_found`, exactly as for an unknown id. Lists for
people without `ai.use` (or `agent.manage`) answer 404 `ai.not_found`, as "my runs"
does. Only its owner changes it (403 `automation.not_allowed` for others who see it):
whoever changes it answers for it. Making one: `placing.py`, and at most
`HERD_AI_AUTOMATIONS_MAX` open ones (active or paused) per person (409
`automation.limit`). Every change bumps `version` (409
`automation.version_conflict` with `current_version` for a stale one) and is
audited with ids only, never the instruction.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require
from app.core.clock import SYSTEM_CLOCK, Clock
from app.core.config import get_settings
from app.core.errors import Conflict, Forbidden, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, encode_id_cursor
from app.modules.agents.repository import AgentRepository
from app.modules.agents.standing import agent_not_found, visible_agent
from app.modules.ai.access import ai_not_found
from app.modules.audit.recorder import record
from app.modules.automations import live, placing
from app.modules.automations.abilities import Abilities, AbilityReader
from app.modules.automations.manage_repository import ManageRepository, Row
from app.modules.automations.models import Automation, AutomationFiring, AutomationState
from app.modules.automations.repository import AutomationRepository
from app.modules.automations.schedule import COLUMNS, Planned, Schedule, plan, upcoming_of
from app.modules.automations.schemas import AutomationCreate, AutomationUpdate
from app.modules.automations.sight import AutomationSight, sight_of
from app.modules.messaging.models import Conversation

CLOCK: Clock = SYSTEM_CLOCK  # tests set one of their own


def automation_not_found() -> NotFound:
    return NotFound(code="automation.not_found")


def version_conflict(current: int) -> Conflict:
    return Conflict(code="automation.version_conflict", details={"current_version": current})


@dataclass(frozen=True, slots=True)
class AutomationView:
    row: Row
    upcoming: list[datetime]
    may_edit: bool
    may_control: bool
    abilities: Abilities


class AutomationService:
    def __init__(self, session: AsyncSession, clock: Clock | None = None) -> None:
        self.session = session
        self.clock = clock or CLOCK

    async def preview(self, actor: Actor, schedule: Schedule) -> list[datetime]:
        if not await can(self.session, actor, Action.AI_USE):
            raise ai_not_found()
        return plan(schedule, self.clock.now()).terms

    async def create(self, actor: Actor, body: AutomationCreate) -> AutomationView:
        if not await can(self.session, actor, Action.AI_USE):
            raise ai_not_found()
        planned = plan(body.schedule, self.clock.now())
        agent = await visible_agent(self.session, actor, body.agent_id)
        place = await placing.find(self.session, actor, agent, body.place)
        await placing.check(self.session, actor, agent, place, planned)
        owned = await ManageRepository(self.session, actor.org_id).hold_owner(actor.principal.id)
        if owned >= get_settings().ai_automations_max:
            raise Conflict(code="automation.limit")
        automation = Automation(
            org_id=actor.org_id,
            owner_user_id=actor.principal.id,
            agent_id=agent.id,
            conversation_id=place.id,
            instruction=body.instruction,
            kind=planned.kind,
            next_due_at=planned.next_due_at,
            state=AutomationState.ACTIVE,
            version=1,
            **planned.columns,
        )
        self.session.add(automation)
        await self.session.flush()
        details = {
            "agent_id": str(agent.id),
            "conversation_id": str(place.id),
            "kind": planned.kind.value,
        }
        await record(
            self.session, actor, "automation.created", "automation", automation.id, details
        )
        await live.changed(self.session, automation, actor, place.space_id)
        return await self.get(actor, automation.id)

    async def get(self, actor: Actor, automation_id: uuid.UUID) -> AutomationView:
        sight = await sight_of(self.session, actor)
        row = await self.repo(actor).one(sight, automation_id) if sight.sees else None
        if row is None:
            raise automation_not_found()
        (view,) = await self.views(actor, sight, [row])
        return view

    async def update(
        self, actor: Actor, automation_id: uuid.UUID, body: AutomationUpdate
    ) -> AutomationView:
        automation, view = await self.locked(actor, automation_id, body.version)
        if not view.may_edit:
            raise Forbidden(code="automation.not_allowed")
        if body.schedule is not None and body.schedule.kind != automation.kind:
            raise ValidationFailed(code="automation.kind_immutable")
        planned = plan(body.schedule, self.clock.now()) if body.schedule else _current(automation)
        agent = await AgentRepository(self.session, actor.org_id).get(automation.agent_id)
        assert agent is not None  # the automation goes with its agent
        place = await AutomationRepository(self.session, actor.org_id).place(automation)
        await placing.check(self.session, actor, agent, place, planned)
        changed = []
        if body.instruction is not None and body.instruction != automation.instruction:
            automation.instruction = body.instruction
            changed.append("instruction")
        if body.schedule is not None:
            _reschedule(automation, planned)
            changed.append("schedule")
        automation.version += 1
        await self.session.flush()
        details = {"fields": changed}
        await record(
            self.session, actor, "automation.updated", "automation", automation.id, details
        )
        await live.changed(self.session, automation, actor, place.space_id)
        return await self.get(actor, automation.id)

    async def mine(self, actor: Actor, params: PageParams) -> Page[AutomationView]:
        sight = await sight_of(self.session, actor)
        if not sight.sees:
            raise ai_not_found()
        return await self._page(
            actor, sight, Automation.owner_user_id == actor.principal.id, params
        )

    async def of_agent(
        self, actor: Actor, agent_id: uuid.UUID, params: PageParams
    ) -> Page[AutomationView]:
        """`agent.manage` only (404 `agent.not_found` for anyone else)."""
        if not await can(self.session, actor, Action.AGENT_MANAGE):
            raise agent_not_found()
        if await AgentRepository(self.session, actor.org_id).get(agent_id) is None:
            raise agent_not_found()
        sight = await sight_of(self.session, actor)
        return await self._page(actor, sight, Automation.agent_id == agent_id, params)

    async def of_space(
        self, actor: Actor, space_id: uuid.UUID, params: PageParams
    ) -> Page[AutomationView]:
        """Those at a place in the space that the caller sees."""
        await require(self.session, actor, Action.SPACE_READ, space_id)
        sight = await sight_of(self.session, actor)
        if not sight.sees:
            raise ai_not_found()
        return await self._page(actor, sight, Conversation.space_id == space_id, params)

    async def log(
        self, actor: Actor, automation_id: uuid.UUID, params: PageParams
    ) -> Page[AutomationFiring]:
        """The automation's terms, newest first."""
        await self.get(actor, automation_id)
        before = decode_id_cursor(params.cursor) if params.cursor else None
        repo = AutomationRepository(self.session, actor.org_id)
        rows = await repo.log_page(automation_id, before, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_id_cursor(items[-1].id) if more else None
        return Page[AutomationFiring](items=items, next_cursor=cursor)

    async def locked(
        self, actor: Actor, automation_id: uuid.UUID, version: int
    ) -> tuple[Automation, AutomationView]:
        """The automation the caller sees, locked, at the version the caller read, and
        how the caller sees it."""
        repo = AutomationRepository(self.session, actor.org_id)
        automation = await repo.get(automation_id, lock=True)
        view = await self.get(actor, automation_id)
        assert automation is not None  # seen
        if automation.version != version:
            raise version_conflict(automation.version)
        return automation, view

    def repo(self, actor: Actor) -> ManageRepository:
        return ManageRepository(self.session, actor.org_id)

    async def views(
        self, actor: Actor, sight: AutomationSight, rows: list[Row]
    ) -> list[AutomationView]:
        managed = set(await self.session.scalars(sight.managed_ids)) if rows else set()
        now = self.clock.now()
        reader = AbilityReader(self.session, actor)
        views = []
        for row in rows:
            owner = row.automation.owner_user_id == sight.person_id
            control = owner or sight.manages_all or row.place.space_id in managed
            abilities = await reader.of(row, owner=owner, control=control)
            upcoming = upcoming_of(row.automation, now)
            views.append(AutomationView(row, upcoming, owner, control, abilities))
        return views

    async def _page(
        self,
        actor: Actor,
        sight: AutomationSight,
        where: ColumnElement[bool],
        params: PageParams,
    ) -> Page[AutomationView]:
        before = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(sight, where, before, params.limit + 1)
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_id_cursor(items[-1].automation.id) if more else None
        return Page[AutomationView](items=await self.views(actor, sight, items), next_cursor=cursor)


def _current(automation: Automation) -> Planned:
    """The stored schedule, for the checks of a change that keeps it."""
    columns = {name: getattr(automation, name) for name in COLUMNS}
    return Planned(automation.kind, columns, [])


def _reschedule(automation: Automation, planned: Planned) -> None:
    for name, value in planned.columns.items():
        setattr(automation, name, value)
    if planned.next_due_at is None:
        return  # an event rule: its quiet time decides when it is due
    automation.next_due_at = planned.next_due_at
    if automation.state == AutomationState.DONE:
        automation.state = AutomationState.ACTIVE  # a `once` given a new instant

"""SQL for attendees (plan M10 task 4). Every statement is scoped by the organisation;
the event's rights are judged before (`invitations.py`), under the event's row lock."""

import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, delete, literal, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_repository import person_reads_space
from app.core.principal import Principal, PrincipalType
from app.modules.agents.models import Agent, AgentStatus
from app.modules.calendars.attendee_models import CalendarEventAttendee, Response
from app.modules.calendars.event_models import CalendarEvent
from app.modules.spaces.models import SpaceMember
from app.modules.users.models import User

Attendee = CalendarEventAttendee


@dataclass(frozen=True, slots=True)
class Listed:
    """An attendee with the name a principal goes by (an address: its own)."""

    attendee: Attendee
    name: str


@dataclass(frozen=True, slots=True)
class Known:
    """Which principals an inviter may name: `everyone` with `directory.read` (else
    only readers of the event's space), agents only with `ai.use` (`agents`), a
    personal agent only its owner's."""

    everyone: bool
    agents: bool


class AttendeeRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    def _of(self, event_id: uuid.UUID) -> ColumnElement[bool]:
        return and_(Attendee.org_id == self.org_id, Attendee.event_id == event_id)

    async def of_event(self, event_id: uuid.UUID) -> list[Attendee]:
        stmt = select(Attendee).where(self._of(event_id)).order_by(Attendee.id)
        return list((await self.session.scalars(stmt)).all())

    async def people_of(self, event_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, list[uuid.UUID]]:
        """The people (not agents, not addresses) invited to each event, in one
        statement."""
        found: dict[uuid.UUID, list[uuid.UUID]] = {event_id: [] for event_id in event_ids}
        if not event_ids:
            return found
        stmt = (
            select(Attendee.event_id, Attendee.principal_id)
            .where(
                Attendee.org_id == self.org_id,
                Attendee.event_id.in_(event_ids),
                Attendee.principal_type == PrincipalType.USER,
            )
            .order_by(Attendee.id)
        )
        for event_id, principal_id in (await self.session.execute(stmt)).all():
            if principal_id is not None:
                found[event_id].append(principal_id)
        return found

    async def page(
        self,
        event_id: uuid.UUID,
        after: uuid.UUID | None,
        limit: int,
        *,
        only: uuid.UUID | None = None,
    ) -> list[Listed]:
        """The event's attendees by id (`only`: that one), with the names of people
        and agents."""
        name = (
            select(User.name)
            .where(
                Attendee.principal_type == PrincipalType.USER,
                User.org_id == self.org_id,
                User.id == Attendee.principal_id,
            )
            .scalar_subquery()
        )
        agent_name = (
            select(Agent.name)
            .where(
                Attendee.principal_type == PrincipalType.AGENT,
                Agent.org_id == self.org_id,
                Agent.id == Attendee.principal_id,
            )
            .scalar_subquery()
        )
        stmt = select(Attendee, name, agent_name).where(self._of(event_id))
        if after is not None:
            stmt = stmt.where(Attendee.id > after)
        if only is not None:
            stmt = stmt.where(Attendee.id == only)
        rows = await self.session.execute(stmt.order_by(Attendee.id).limit(limit))
        return [Listed(row[0], row[1] or row[2] or row[0].name) for row in rows]

    async def mine(self, event_id: uuid.UUID, principal: Principal) -> Attendee | None:
        """The principal's row on the event, locked."""
        stmt = (
            select(Attendee)
            .where(
                self._of(event_id),
                Attendee.principal_type == principal.type,
                Attendee.principal_id == principal.id,
            )
            .with_for_update()
        )
        found: Attendee | None = await self.session.scalar(stmt)
        return found

    async def invites(self, event_id: uuid.UUID, principal: Principal) -> bool:
        """Whether the principal has a row on the event (a tombstone's too)."""
        stmt = select(Attendee.id).where(
            self._of(event_id),
            Attendee.principal_type == principal.type,
            Attendee.principal_id == principal.id,
        )
        return await self.session.scalar(stmt) is not None

    async def known(
        self, principals: Iterable[Principal], *, space_id: uuid.UUID, viewer: uuid.UUID, may: Known
    ) -> set[Principal]:
        """Which of `principals` the inviter may name (`may`): active people of the
        organisation (without `directory.read`: those who read the space), agents
        that are not drafts (without `directory.read`: the space's members; a personal
        one only its owner's)."""
        users = [p.id for p in principals if p.type == PrincipalType.USER]
        agents = [p.id for p in principals if p.type == PrincipalType.AGENT]
        found: set[Principal] = set()
        if users:
            people = select(User.id).where(
                User.org_id == self.org_id, User.id.in_(users), User.is_active.is_(True)
            )
            if not may.everyone:
                people = people.where(person_reads_space(literal(space_id)))
            found |= {Principal.user(i) for i in (await self.session.scalars(people)).all()}
        if agents and may.agents:
            stmt = select(Agent.id).where(
                Agent.org_id == self.org_id,
                Agent.id.in_(agents),
                Agent.status != AgentStatus.DRAFT,
                or_(Agent.owner_user_id.is_(None), Agent.owner_user_id == viewer),
            )
            if not may.everyone:
                member = select(SpaceMember.member_id).where(
                    SpaceMember.space_id == space_id,
                    SpaceMember.member_type == PrincipalType.AGENT,
                    SpaceMember.member_id == Agent.id,
                )
                stmt = stmt.where(member.exists())
            found |= {Principal.agent(i) for i in (await self.session.scalars(stmt)).all()}
        return found

    async def copy(self, source_id: uuid.UUID, target_id: uuid.UUID) -> None:
        """The attendees of `source` and their answers, onto `target` (which has none)."""
        for attendee in await self.of_event(source_id):
            self.session.add(
                Attendee(
                    org_id=self.org_id,
                    event_id=target_id,
                    principal_type=attendee.principal_type,
                    principal_id=attendee.principal_id,
                    email=attendee.email,
                    name=attendee.name,
                    role=attendee.role,
                    response=attendee.response,
                )
            )
        await self.session.flush()

    async def reset(self, event_id: uuid.UUID, keep: Principal) -> None:
        """Every answer of the event back to `needs_action`, but `keep`'s and the
        agents' (who are always accepted)."""
        await self.session.execute(
            update(Attendee)
            .where(
                self._of(event_id),
                Attendee.response != Response.NEEDS_ACTION,
                or_(
                    Attendee.principal_type.is_(None), Attendee.principal_type == PrincipalType.USER
                ),
                or_(
                    Attendee.principal_id.is_(None),
                    Attendee.principal_type != keep.type,
                    Attendee.principal_id != keep.id,
                ),
            )
            .values(response=Response.NEEDS_ACTION)
            .execution_options(synchronize_session="fetch")
        )

    async def follow(
        self, series_id: uuid.UUID, principal: Principal, old: Response, new: Response
    ) -> None:
        """The principal's answer on each live override of the series that still holds
        its old answer on the series: `new`."""
        overrides = select(CalendarEvent.id).where(
            CalendarEvent.org_id == self.org_id,
            CalendarEvent.series_id == series_id,
            CalendarEvent.deleted_at.is_(None),
        )
        await self.session.execute(
            update(Attendee)
            .where(
                Attendee.org_id == self.org_id,
                Attendee.event_id.in_(overrides),
                Attendee.principal_type == principal.type,
                Attendee.principal_id == principal.id,
                Attendee.response == old,
            )
            .values(response=new)
            .execution_options(synchronize_session="fetch")
        )

    async def remove(self, attendees: Iterable[Attendee]) -> None:
        ids = [attendee.id for attendee in attendees]
        if ids:
            await self.session.execute(
                delete(Attendee)
                .where(and_(Attendee.org_id == self.org_id, Attendee.id.in_(ids)))
                .execution_options(synchronize_session="fetch")
            )

    async def add(self, attendees: Iterable[Attendee]) -> None:
        self.session.add_all(list(attendees))
        await self.session.flush()

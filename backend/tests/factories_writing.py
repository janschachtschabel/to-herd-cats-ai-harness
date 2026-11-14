"""Fixtures for the writing tools (plan M6 task 6): `work`, a team space where Alice
and the bench's agent are editors (the admin too), plus a space only Alice may read
(`private`), and helpers to read what the tools wrote."""

import uuid
from dataclasses import dataclass
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.core.permissions import SpaceRole
from app.modules.messaging.models import Message
from app.modules.spaces.models import Space, SpaceKind
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_wiki import new_page, publish


@dataclass
class Work:
    bench: Bench
    space: Space  # Alice, the admin and the agent are editors
    private: Space  # Alice only: the agent is no member

    @property
    def admin(self) -> Any:
        return self.bench.people.admin

    async def page(self, title: str = "Regeln", content_md: str = "eins\nzwei\n") -> str:
        made = await new_page(self.admin, self.space.id, title, content_md=content_md)
        return str((await publish(self.admin, made))["id"])

    async def ticket(self, title: str = "Aufgabe", **fields: Any) -> dict[str, Any]:
        return await new_ticket(self.admin, self.space.id, title, **fields)


@pytest.fixture
async def work(bench: Bench, make_space: MakeSpace) -> Work:
    alice, admin = bench.people.users["alice"], bench.people.users["admin"]
    members = [(alice, SpaceRole.EDITOR), (admin, SpaceRole.EDITOR)]
    space = await make_space(SpaceKind.TEAM, name="Werkstatt", members=members)
    await bench.join(space, SpaceRole.EDITOR)
    private = await make_space(SpaceKind.TEAM, name="Geheim", members=members)
    return Work(bench, space, private)


async def set_level(bench: Bench, level: int) -> None:
    bench.agent.level = level
    await bench.session.flush()


async def events(session: AsyncSession, type_: str) -> list[EventOutbox]:
    stmt = select(EventOutbox).where(EventOutbox.type == type_).order_by(EventOutbox.id)
    return list((await session.scalars(stmt)).all())


async def messages_in(session: AsyncSession, conversation_id: uuid.UUID) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.scalars(stmt)).all())

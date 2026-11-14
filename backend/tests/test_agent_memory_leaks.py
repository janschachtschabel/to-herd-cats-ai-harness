"""Plan M6 task 9, review focus 1: memory from team space A never reaches an audience
that cannot read A: not in a channel of B, not in a DM with someone outside A, not
after the agent left A, and not once the page was moved or put into the trash."""

import pytest
from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.core.principal import Principal, PrincipalType
from app.modules.agents import memory
from app.modules.agents.models import StopReason
from app.modules.agents.run_repository import RunRepository
from app.modules.ai.models import DataLocation
from app.modules.messaging.models import Message, MessageKind
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.wiki.models import Page
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_tools import tool_context
from tests.test_agent_memory import remember
from tests.test_run_scope_places import actor_in, channel_in, dm_of

SECRET = "Okapi-A-91"


@pytest.fixture
async def rooms(bench: Bench, make_space: MakeSpace) -> dict[str, Space]:
    """`a`: Alice and the agent (editors), with the agent's memory holding SECRET;
    `b`: Alice, Bob and the agent (editors)."""
    u = bench.people.users
    a = await make_space(SpaceKind.TEAM, "A", members=[(u["alice"], SpaceRole.EDITOR)])
    b = await make_space(
        SpaceKind.TEAM,
        "B",
        members=[(u["alice"], SpaceRole.EDITOR), (u["bob"], SpaceRole.EDITOR)],
    )
    for space in (a, b):
        await bench.join(space, SpaceRole.EDITOR)
    text = await remember(await tool_context(bench), a.id, f"Merke: {SECRET}")
    assert "saved" in text, text
    return {"a": a, "b": b}


async def _memory(bench: Bench, conversation_id: object, place: Space | None = None) -> str:
    actor = await actor_in(bench, conversation_id)
    found = await memory.for_run(
        bench.session, actor, bench.agent.id, DataLocation.LOCAL, place.id if place else None
    )
    return found.text or ""


async def _page(bench: Bench) -> Page:
    page = await bench.session.scalar(select(Page).where(Page.title == "Gedächtnis"))
    assert page is not None
    return page


async def test_alone_with_the_agent_alice_gets_it(bench: Bench, rooms: dict[str, Space]) -> None:
    assert SECRET in await _memory(bench, bench.dm_id)


async def test_not_in_a_channel_of_another_space(bench: Bench, rooms: dict[str, Space]) -> None:
    channel = await channel_in(bench, rooms["b"])
    assert SECRET not in await _memory(bench, channel.id, rooms["b"])
    in_a = await channel_in(bench, rooms["a"])
    assert SECRET in await _memory(bench, in_a.id, rooms["a"])


async def test_not_in_a_dm_with_someone_outside_the_space(
    bench: Bench, rooms: dict[str, Space]
) -> None:
    """The whole run path: Bob reads B, not A; the provider never gets A's memory."""
    dm = await dm_of(bench, "alice", "bob")
    assert SECRET not in await _memory(bench, dm.id)
    alice = bench.people.users["alice"]
    message = Message(
        org_id=dm.org_id,
        conversation_id=dm.id,
        author_type=PrincipalType.USER,
        author_id=alice.id,
        kind=MessageKind.HUMAN,
        body_md="Was weißt du?",
    )
    bench.session.add(message)
    await bench.session.flush()
    await RunRepository(bench.session, dm.org_id).enqueue(
        bench.agent.id, alice.id, dm.id, message.id
    )
    assert await bench.run_next() == StopReason.COMPLETED
    assert SECRET not in bench.stub.state.texts()


async def test_not_after_the_agent_left_the_space(bench: Bench, rooms: dict[str, Space]) -> None:
    await SpaceRepository(bench.session).remove_member(
        rooms["a"].id, Principal.agent(bench.agent.id)
    )
    assert SECRET not in await _memory(bench, bench.dm_id)
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.COMPLETED
    assert SECRET not in bench.stub.state.texts()


async def test_not_once_the_page_was_moved_or_trashed(
    bench: Bench, rooms: dict[str, Space]
) -> None:
    page = await _page(bench)
    admin = bench.people.admin
    await SpaceRepository(bench.session).set_member(
        rooms["a"].id, Principal.user(bench.people.users["admin"].id), SpaceRole.EDITOR
    )
    r = await admin.post(f"/api/pages/{page.id}/move", json={"parent_id": None, "version": 1})
    assert r.status_code == 200, r.text  # moved within A: still A's, still A's audience
    channel = await channel_in(bench, rooms["b"])
    assert SECRET not in await _memory(bench, channel.id, rooms["b"])
    assert SECRET in await _memory(bench, bench.dm_id)
    page = await _page(bench)
    page.space_id = rooms["b"].id  # no path moves a page between spaces; were there one,
    await bench.session.flush()  # it would no longer be A's memory, nor B's
    assert SECRET not in await _memory(bench, channel.id, rooms["b"])
    assert SECRET not in await _memory(bench, bench.dm_id)
    page.space_id = rooms["a"].id
    await bench.session.flush()
    page = await _page(bench)
    r = await admin.post(f"/api/pages/{page.id}/trash", json={"version": page.version})
    assert r.status_code == 204, r.text
    assert SECRET not in await _memory(bench, bench.dm_id)


async def test_not_when_the_page_is_locked_for_ai(bench: Bench, rooms: dict[str, Space]) -> None:
    page = await _page(bench)
    page.no_ai = True
    await bench.session.flush()
    assert SECRET not in await _memory(bench, bench.dm_id)

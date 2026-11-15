"""Plan M6 task 3 (spec 5.6, decision 5): a run reads only what the audience of its
place may see, and writes only where its place lets it: a DM alone with the agent
(the person's rights ∩ the agent), a DM with several people (what all of them read),
a channel or a page or ticket thread in S (S and the open spaces; S only while S has
guests). Leak tests per place, through the one permission check and the tools, and
through a whole run in a DM with several people."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can, require
from app.core.errors import Forbidden, NotFound
from app.core.permissions import SpaceRole
from app.core.principal import PrincipalType
from app.modules.agents.actor import Reads, run_actor
from app.modules.agents.run_models import StopReason
from app.modules.agents.run_repository import RunRepository
from app.modules.agents.toolbox.base import RunRef, ToolContext
from app.modules.agents.toolbox.reading import SearchArgs, search
from app.modules.ai.models import DataLocation
from app.modules.messaging.models import (
    Conversation,
    ConversationKind,
    ConversationParticipant,
    Message,
    MessageKind,
)
from app.modules.messaging.thread_repository import PageThreadRepository
from app.modules.spaces.models import Space, SpaceKind
from app.modules.tickets.models import WorkItem
from app.modules.tickets.thread_repository import TicketThreadRepository
from app.modules.wiki.models import Page
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_wiki import new_page, publish

SECRET = "Okapi77"


@pytest.fixture
async def places(bench: Bench, make_space: MakeSpace) -> dict[str, Space]:
    """`s` and `t`: team spaces of Alice, Bob and the agent (editors); `o`: an open
    space where Alice and the agent are editors; `g`: a team space of Alice, the
    agent and the guest. Each holds a page whose title names it."""
    u = bench.people.users
    a, b, gast = u["alice"], u["bob"], u["gast"]
    made = {
        "s": await make_space(
            SpaceKind.TEAM, members=[(a, SpaceRole.EDITOR), (b, SpaceRole.EDITOR)]
        ),
        "t": await make_space(
            SpaceKind.TEAM, members=[(a, SpaceRole.EDITOR), (b, SpaceRole.EDITOR)]
        ),
        "o": await make_space(SpaceKind.OPEN, members=[(a, SpaceRole.EDITOR)]),
        "g": await make_space(
            SpaceKind.TEAM, members=[(a, SpaceRole.EDITOR), (gast, SpaceRole.VIEWER)]
        ),
    }
    for name, space in made.items():
        await bench.join(space, SpaceRole.EDITOR)
        admin = bench.people.admin
        await publish(admin, await new_page(admin, space.id, f"Zebra {name}", content_md=SECRET))
    return made


async def channel_in(bench: Bench, space: Space) -> Conversation:
    conversation = Conversation(
        org_id=space.org_id, kind=ConversationKind.CHANNEL, space_id=space.id, name="c"
    )
    bench.session.add(conversation)
    await bench.session.flush()
    return conversation


async def thread_in(bench: Bench, space: Space, kind: str) -> Conversation:
    if kind == "channel":
        return await channel_in(bench, space)
    session, org = bench.session, space.org_id
    if kind == "page":
        page = await new_page(bench.people.admin, space.id, "Thread page")
        row = await session.get(Page, uuid.UUID(page["id"]))
        assert row is not None
        return await PageThreadRepository(session, org).thread_for(row)
    ticket = await new_ticket(bench.people.admin, space.id, "Thread ticket")
    item = await session.get(WorkItem, uuid.UUID(ticket["id"]))
    assert item is not None
    return await TicketThreadRepository(session, org).thread_for(item)


async def dm_of(bench: Bench, *names: str) -> Conversation:
    """A DM of these people and the agent (rows; the API pairs an agent with one)."""
    session = bench.session
    org = bench.agent.org_id
    conversation = Conversation(org_id=org, kind=ConversationKind.DM, dm_key=uuid.uuid4().hex)
    session.add(conversation)
    await session.flush()
    members = [(PrincipalType.USER, bench.people.users[n].id) for n in names]
    for kind, principal_id in [*members, (PrincipalType.AGENT, bench.agent.id)]:
        session.add(
            ConversationParticipant(
                org_id=org,
                conversation_id=conversation.id,
                principal_type=kind,
                principal_id=principal_id,
            )
        )
    await session.flush()
    return conversation


async def actor_in(bench: Bench, conversation_id: object) -> Actor:
    actor = await run_actor(
        bench.session,
        bench.agent.org_id,
        bench.people.users["alice"].id,
        bench.agent.id,
        conversation_id,  # type: ignore[arg-type]
    )
    assert actor is not None
    return actor


async def readable(session: AsyncSession, actor: Actor, places: dict[str, Space]) -> set[str]:
    return {n for n, s in places.items() if await can(session, actor, Action.SPACE_READ, s.id)}


async def writable(session: AsyncSession, actor: Actor, places: dict[str, Space]) -> set[str]:
    return {n for n, s in places.items() if await can(session, actor, Action.PAGE_EDIT, s.id)}


async def found(bench: Bench, actor: Actor) -> set[str]:
    ctx = ToolContext(
        bench.session,
        actor,
        DataLocation.LOCAL,
        Reads(),
        RunRef(uuid.uuid4(), actor.org_id, bench.agent.id, actor.principal.id, uuid.uuid4()),
    )
    result = await search(ctx, SearchArgs(query="Zebra"))
    return {name for name in "stog" if f"Zebra {name}" in result.text}


async def test_alone_with_the_agent_the_persons_rights_count(
    bench: Bench, places: dict[str, Space]
) -> None:
    actor = await actor_in(bench, bench.dm_id)
    assert await readable(bench.session, actor, places) == {"s", "t", "o", "g"}
    assert await writable(bench.session, actor, places) == {"s", "t", "o", "g"}
    assert actor.write_scope is None
    assert await found(bench, actor) == {"s", "t", "o", "g"}


@pytest.mark.parametrize("kind", ["channel", "page", "ticket"])
async def test_in_a_place_of_s_only_s_and_the_open_spaces(
    bench: Bench, places: dict[str, Space], kind: str
) -> None:
    actor = await actor_in(bench, (await thread_in(bench, places["s"], kind)).id)
    assert await readable(bench.session, actor, places) == {"s", "o"}
    assert await writable(bench.session, actor, places) == {"s"}
    assert await found(bench, actor) == {"s", "o"}
    assert not await can(bench.session, actor, Action.CHANNEL_POST, places["o"].id)
    with pytest.raises(Forbidden):  # read, but not written: outside the place's space
        await require(bench.session, actor, Action.PAGE_CREATE, places["o"].id)
    with pytest.raises(NotFound):  # not even there for it
        await require(bench.session, actor, Action.PAGE_CREATE, places["t"].id)


async def test_in_a_place_of_an_open_space_only_open_spaces(
    bench: Bench, places: dict[str, Space]
) -> None:
    actor = await actor_in(bench, (await channel_in(bench, places["o"])).id)
    assert await readable(bench.session, actor, places) == {"o"}
    assert await writable(bench.session, actor, places) == {"o"}
    assert await found(bench, actor) == {"o"}


async def test_a_space_with_guests_shows_no_open_space(
    bench: Bench, places: dict[str, Space]
) -> None:
    actor = await actor_in(bench, (await channel_in(bench, places["g"])).id)
    assert await readable(bench.session, actor, places) == {"g"}
    assert await found(bench, actor) == {"g"}


async def test_a_dm_of_several_people_reads_what_all_of_them_read(
    bench: Bench, places: dict[str, Space]
) -> None:
    with_bob = await actor_in(bench, (await dm_of(bench, "alice", "bob")).id)
    assert await readable(bench.session, with_bob, places) == {"s", "t", "o"}
    assert await writable(bench.session, with_bob, places) == {"s", "t", "o"}
    assert await found(bench, with_bob) == {"s", "t", "o"}
    with_guest = await actor_in(bench, (await dm_of(bench, "alice", "gast")).id)
    assert await readable(bench.session, with_guest, places) == {"g"}  # no open space
    bench.people.users["bob"].is_active = False
    await bench.session.flush()
    alone_now = await actor_in(bench, (await dm_of(bench, "alice", "bob")).id)
    assert alone_now.write_scope is None  # only Alice still acts: alone with the agent


async def test_a_run_in_a_dm_with_several_people_never_reads_past_them(
    bench: Bench, places: dict[str, Space]
) -> None:
    """The whole run path: Bob is no member of `g`, so its page is not read and its
    content never reaches the provider, though Alice and the agent may read it."""
    dm = await dm_of(bench, "alice", "bob")
    alice = bench.people.users["alice"]
    session = bench.session
    message = Message(
        org_id=dm.org_id,
        conversation_id=dm.id,
        author_type=PrincipalType.USER,
        author_id=alice.id,
        kind=MessageKind.HUMAN,
        body_md="What is in g?",
    )
    session.add(message)
    await session.flush()
    await RunRepository(session, dm.org_id).enqueue(bench.agent.id, alice.id, dm.id, message.id)
    page_g = await _page_titled(bench, "Zebra g")
    page_s = await _page_titled(bench, "Zebra s")
    bench.stub.state.replies.extend(
        [
            {"tool_calls": [{"name": "read_page", "arguments": {"page_id": page_g}}]},
            {"tool_calls": [{"name": "read_page", "arguments": {"page_id": page_s}}]},
            {"content": "Done."},
        ]
    )
    assert await bench.run_next() == StopReason.COMPLETED
    sent = bench.stub.state.texts()
    assert sent.count(SECRET) == 1  # the page of s only, not the one of g
    assert "Nothing found (or not readable)." in sent


async def _page_titled(bench: Bench, title: str) -> str:
    page_id = await bench.session.scalar(select(Page.id).where(Page.title == title))
    assert page_id is not None
    return str(page_id)

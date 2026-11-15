"""Plan M8 task 2 (decisions 3 and 4): the read tools over `/mcp`, with a real MCP
client. A token reads only the spaces of its scope that its person may read and
whose AI policy lets the organisation's MCP data location receive them; never a
draft, never a page locked for AI; whatever it may not read answers exactly like an
unknown id."""

import uuid
from dataclasses import dataclass
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.modules.ai.models import AiPolicy, DataLocation
from app.modules.spaces.models import Space, SpaceKind
from app.modules.users.models import User
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_tokens import mcp_on, new_token
from tests.factories_wiki import new_page, publish

NOT_FOUND = "Nothing found (or not readable)."


@dataclass
class World:
    spaces: dict[str, Space]
    pages: dict[str, dict[str, Any]]
    tickets: dict[str, dict[str, Any]]


async def _world(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> World:
    mine = [(member, SpaceRole.EDITOR)]
    spaces = {
        "any": await make_space(SpaceKind.TEAM, "Offen", mine),
        "none": await make_space(SpaceKind.TEAM, "Ohne KI", mine),
        "eu": await make_space(SpaceKind.TEAM, "Nur EU", mine),
        "elsewhere": await make_space(SpaceKind.TEAM, "Fremd"),
    }
    pages: dict[str, dict[str, Any]] = {}
    for name in ("any", "none", "eu"):
        space_id = spaces[name].id
        page = await new_page(member_client, space_id, f"Zebra {name}", content_md="Zebrastreifen")
        pages[name] = await publish(member_client, page)
    pages["elsewhere"] = await publish(
        owner, await new_page(owner, spaces["elsewhere"].id, "Zebra fremd", content_md="Zebra")
    )
    pages["draft"] = await new_page(
        member_client, spaces["any"].id, "Zebra Entwurf", content_md="Zebrastreifen geheim"
    )
    locked = await publish(
        member_client,
        await new_page(member_client, spaces["any"].id, "Zebra gesperrt", content_md="Zebra"),
    )
    r = await owner.put(
        f"/api/pages/{locked['id']}/ai-lock", json={"no_ai": True, "version": locked["version"]}
    )
    assert r.status_code == 200, r.text
    pages["locked"] = locked
    tickets = {
        name: await new_ticket(member_client, spaces[name].id, f"Zebra-Ticket {name}")
        for name in ("any", "none", "eu")
    }
    tickets["elsewhere"] = await new_ticket(owner, spaces["elsewhere"].id, "Zebra-Ticket fremd")
    spaces["none"].ai_policy = AiPolicy.NONE
    spaces["eu"].ai_policy = AiPolicy.RESTRICTED
    spaces["eu"].allowed_locations = [DataLocation.EU.value]
    await session.flush()
    return World(spaces, pages, tickets)


def _key(ticket: dict[str, Any]) -> str:
    return f"HC-{ticket['number']}"


async def test_a_token_reads_only_what_its_person_scope_and_policy_allow(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
    connect: Connect,
) -> None:
    world = await _world(session, owner, member_client, member, make_space)
    await mcp_on(owner)  # external
    token = await new_token(member_client)
    async with connect(token["secret"]) as client:
        spaces = text_of(await client.call_tool("list_tree", {}))
        found = text_of(await client.call_tool("search", {"query": "Zebra"}))
        pages = {
            name: text_of(await client.call_tool("read_page", {"page_id": page["id"]}))
            for name, page in world.pages.items()
        }
        unknown = text_of(await client.call_tool("read_page", {"page_id": str(uuid.uuid4())}))
        tickets = {
            name: text_of(await client.call_tool("read_ticket", {"key": _key(ticket)}))
            for name, ticket in world.tickets.items()
        }
        free = text_of(await client.call_tool("read_ticket", {"key": "HC-99999"}))
        listed = text_of(await client.call_tool("search_tickets", {"query": "Zebra"}))
        tree = text_of(
            await client.call_tool("list_tree", {"space_id": str(world.spaces["any"].id)})
        )
        shut_tree = await client.call_tool("list_tree", {"space_id": str(world.spaces["none"].id)})

    assert "Offen" in spaces
    for hidden in ("Ohne KI", "Nur EU", "Fremd"):
        assert hidden not in spaces
    assert "Zebra any" in found
    for hidden in ("Zebra none", "Zebra eu", "Zebra fremd", "Entwurf", "gesperrt", "geheim"):
        assert hidden not in found
    assert "Zebrastreifen" in pages["any"]
    assert unknown == NOT_FOUND
    for name in ("none", "eu", "elsewhere", "draft", "locked"):
        assert pages[name] == unknown, name  # exactly like an unknown id
    assert "Zebra-Ticket any" in tickets["any"]
    for name in ("none", "eu", "elsewhere"):
        assert tickets[name] == free, name
    assert "Zebra-Ticket any" in listed
    for name in ("none", "eu", "fremd"):
        assert f"Zebra-Ticket {name}" not in listed
    assert "Zebra any" in tree
    assert "Entwurf" not in tree and "gesperrt" not in tree and "draft" not in tree
    assert text_of(shut_tree) == NOT_FOUND and not shut_tree.is_error


async def test_the_scope_of_a_token_narrows_and_the_data_location_widens(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
    connect: Connect,
) -> None:
    world = await _world(session, owner, member_client, member, make_space)
    await mcp_on(owner, data_location="eu")  # the clients run in the house
    everything = await new_token(member_client)
    listed = await new_token(member_client, space_ids=[str(world.spaces["none"].id)])
    async with connect(everything["secret"]) as client:
        eu = text_of(await client.call_tool("read_page", {"page_id": world.pages["eu"]["id"]}))
        none = text_of(await client.call_tool("read_page", {"page_id": world.pages["none"]["id"]}))
    async with connect(listed["secret"]) as client:
        outside = text_of(
            await client.call_tool("read_page", {"page_id": world.pages["any"]["id"]})
        )
        found = text_of(await client.call_tool("search", {"query": "Zebra"}))
    assert "Zebrastreifen" in eu
    assert none == NOT_FOUND  # policy `none`: never through `/mcp`
    assert outside == NOT_FOUND  # outside the token's scope
    assert found == NOT_FOUND  # its one space is shut by policy


async def test_a_space_taken_from_the_person_is_gone_at_the_next_call(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
    connect: Connect,
) -> None:
    world = await _world(session, owner, member_client, member, make_space)
    await mcp_on(owner)
    token = await new_token(member_client)
    page_id = world.pages["any"]["id"]
    space_id = world.spaces["any"].id
    async with connect(token["secret"]) as client:
        before = text_of(await client.call_tool("read_page", {"page_id": page_id}))
        r = await owner.delete(f"/api/spaces/{space_id}/members/user/{member.id}")
        assert r.status_code == 204, r.text
        after = text_of(await client.call_tool("read_page", {"page_id": page_id}))
    assert "Zebrastreifen" in before
    assert after == NOT_FOUND


async def test_versions_need_the_right_to_edit_and_never_show_a_draft(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
    connect: Connect,
) -> None:
    """The history needs `page.edit`, as for a person (spec 9): a `read` token writes
    nowhere, so it never has it; a `write` token has it where its person does."""
    world = await _world(session, owner, member_client, member, make_space)
    await mcp_on(owner)
    reading = await new_token(member_client)
    writing = await new_token(member_client, mode="write")
    page = {"page_id": world.pages["any"]["id"]}
    async with connect(reading["secret"]) as client:
        refused = await client.call_tool("list_versions", page)
    async with connect(writing["secret"]) as client:
        shown = await client.call_tool("list_versions", page)
        draft = await client.call_tool("list_versions", {"page_id": world.pages["draft"]["id"]})
    assert text_of(refused) == NOT_FOUND
    assert "version 1" in text_of(shown)
    assert text_of(draft) == NOT_FOUND

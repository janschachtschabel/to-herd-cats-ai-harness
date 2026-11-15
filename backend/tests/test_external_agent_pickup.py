"""Plan M8 task 4 (decision 12; acceptance, spec 14): an external agent picks a ticket
up through `/mcp` and brings it to review, never to done. `list_my_tickets` lists
what is assigned to it and not finished; `claim_ticket` takes an unassigned ticket
(or its own) into the first `active` status, with the version: of two agents only
one gets it. Everything it does is the agent's, with the AI mark, in the ticket's
thread and timeline, and counted in its token's calls."""

from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorship import Authorship
from app.core.errors import Conflict
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import Agent, Run
from app.modules.spaces.models import SpaceKind
from app.modules.tickets.claiming import TicketClaims
from tests.factories_external_agents import agent_token, make_external
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_tokens import mcp_on
from tests.factories_writing import Work
from tests.test_access import actor_of
from tests.ticket_thread_helpers import ticket_handlers

NOT_FOUND = "Nothing found (or not readable)."


async def _statuses(work: Work) -> dict[str, dict[str, Any]]:
    r = await work.admin.get(f"/api/spaces/{work.space.id}/ticket-statuses")
    found: dict[str, dict[str, Any]] = {}
    for status in r.json()["items"]:
        found.setdefault(status["category"], status)
    return found


async def _assign(work: Work, ticket: dict[str, Any], agent: Agent) -> dict[str, Any]:
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}",
        json={"version": ticket["version"], "assignee": {"type": "agent", "id": str(agent.id)}},
    )
    assert r.status_code == 200, r.text
    changed: dict[str, Any] = r.json()
    return changed


async def _ticket(work: Work, number: int) -> dict[str, Any]:
    shown: dict[str, Any] = (await work.admin.get(f"/api/tickets/{number}")).json()
    return shown


async def test_an_external_agent_brings_a_ticket_to_review_never_to_done(
    work: Work, connect: Connect, session: AsyncSession
) -> None:
    await mcp_on(work.admin)
    agent = await make_external(work)
    statuses = await _statuses(work)
    ticket = await _assign(work, await work.ticket("Abholen"), agent)
    assert ticket["awaiting_pickup"] is True
    token = await agent_token(work.admin, agent, space_ids=[str(work.space.id)])
    key = ticket["key"]
    async with connect(token["secret"]) as client:
        mine = await client.call_tool("list_my_tickets", {})
        claimed = await client.call_tool("claim_ticket", {"key": key, "version": ticket["version"]})
        commented = await client.call_tool("comment_ticket", {"key": key, "text": "Fertig."})
        review = await client.call_tool(
            "set_ticket_status", {"key": key, "status": statuses["review"]["name"]}
        )
        done = await client.call_tool(
            "set_ticket_status", {"key": key, "status": statuses["done"]["name"]}
        )
    assert key in text_of(mine) and f"version={ticket['version']}" in text_of(mine)
    assert not claimed.is_error, text_of(claimed)
    assert not commented.is_error and not review.is_error
    assert done.is_error and "done" in text_of(done)
    shown = await _ticket(work, ticket["number"])
    assert shown["status"]["id"] == statuses["review"]["id"]
    assert shown["assignee"]["id"] == str(agent.id) and shown["awaiting_pickup"] is False
    assert int(await session.scalar(select(func.count()).select_from(Run)) or 0) == 0
    await ticket_handlers(session)
    thread = (await work.admin.get(f"/api/tickets/{ticket['number']}/thread")).json()
    messages = (await work.admin.get(f"/api/conversations/{thread['id']}/messages")).json()
    changed = [
        m
        for m in messages["items"]
        if m["kind"] == "system" and m["system"]["key"] == "ticket.status_changed"
    ]
    assert len(changed) == 2  # claimed (open → active), then review
    for entry in changed:
        assert entry["system"]["actor"]["id"] == str(agent.id)
        assert entry["via_token"] == "Codex"
    calls = (await work.admin.get(f"/api/agents/{agent.id}/tokens/{token['id']}/calls")).json()
    assert [c["tool"] for c in reversed(calls["items"])] == [
        "list_my_tickets",
        "claim_ticket",
        "comment_ticket",
        "set_ticket_status",
        "set_ticket_status",
    ]
    assert [c["outcome"] for c in calls["items"]][0] == "refused"


async def test_two_agents_cannot_both_claim_a_ticket(
    work: Work, connect: Connect, session: AsyncSession
) -> None:
    await mcp_on(work.admin)
    first, second = await make_external(work), await make_external(work, name="Zweit")
    ticket = await work.ticket("Begehrt")
    tokens = [await agent_token(work.admin, agent) for agent in (first, second)]
    async with connect(tokens[0]["secret"]) as client:
        won = await client.call_tool(
            "claim_ticket", {"key": ticket["key"], "version": ticket["version"]}
        )
    async with connect(tokens[1]["secret"]) as client:
        taken = await client.call_tool(
            "claim_ticket", {"key": ticket["key"], "version": ticket["version"]}
        )
    assert not won.is_error
    assert taken.is_error and "someone else" in text_of(taken)
    shown = await _ticket(work, ticket["number"])
    assert shown["assignee"]["id"] == str(first.id)
    assert shown["status"]["category"] == "active"
    # the service itself, for the second claim as it races the first: the version it
    # read is stale (it waited on the row lock), or, read anew, the ticket is taken
    actor = await actor_of(session, work.bench.people.users["alice"])
    claims, me = TicketClaims(session), Principal.agent(second.id)
    by = Authorship(me, via_token="Codex")
    with pytest.raises(Conflict) as stale:
        await claims.claim(actor, ticket["number"], ticket["version"], me, by)
    with pytest.raises(Conflict) as lost:
        await claims.claim(actor, ticket["number"], shown["version"], me, by)
    assert (stale.value.code, lost.value.code) == ("ticket.version_conflict", "ticket.taken")


async def test_a_stale_version_is_a_tool_error(work: Work, connect: Connect) -> None:
    await mcp_on(work.admin)
    agent = await make_external(work)
    ticket = await work.ticket("Alt")
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}", json={"version": ticket["version"], "title": "Neu"}
    )
    assert r.status_code == 200, r.text
    token = await agent_token(work.admin, agent)
    async with connect(token["secret"]) as client:
        stale = await client.call_tool(
            "claim_ticket", {"key": ticket["key"], "version": ticket["version"]}
        )
    assert stale.is_error
    assert text_of(stale) == "Changed meanwhile (ticket.version_conflict): read it again."
    assert (await _ticket(work, ticket["number"]))["assignee"] is None


async def test_what_cannot_be_claimed(work: Work, connect: Connect, make_space: MakeSpace) -> None:
    await mcp_on(work.admin)
    agent = await make_external(work)
    statuses = await _statuses(work)
    alice = work.bench.people.users["alice"]
    theirs = await work.ticket("Alices")
    r = await work.admin.patch(
        f"/api/tickets/{theirs['number']}",
        json={"version": theirs["version"], "assignee": {"type": "user", "id": str(alice.id)}},
    )
    assert r.status_code == 200, r.text
    finished = await work.ticket("Fertig")
    r = await work.admin.patch(
        f"/api/tickets/{finished['number']}",
        json={"version": finished["version"], "status_id": statuses["done"]["id"]},
    )
    assert r.status_code == 200, r.text
    elsewhere = await make_space(SpaceKind.TEAM, members=[(alice, SpaceRole.EDITOR)])
    hidden = await new_ticket(work.admin, elsewhere.id, "Woanders")
    token = await agent_token(work.admin, agent)
    async with connect(token["secret"]) as client:
        results = {
            name: await client.call_tool("claim_ticket", {"key": t["key"]})
            for name, t in (("theirs", theirs), ("finished", finished), ("hidden", hidden))
        }
        unknown = await client.call_tool("claim_ticket", {"key": "HC-9999"})
    assert "someone else" in text_of(results["theirs"])
    assert text_of(results["finished"]) == "Refused (ticket.not_claimable)."
    assert text_of(results["hidden"]) == NOT_FOUND == text_of(unknown)
    assert all(r.is_error for r in [*results.values(), unknown])


async def test_list_my_tickets_shows_only_its_unfinished_ones(work: Work, connect: Connect) -> None:
    await mcp_on(work.admin)
    agent = await make_external(work)
    other = await make_external(work, name="Andere")
    statuses = await _statuses(work)
    open_one = await _assign(work, await work.ticket("Offen"), agent)
    done_one = await _assign(work, await work.ticket("Erledigt"), agent)
    r = await work.admin.patch(
        f"/api/tickets/{done_one['number']}",
        json={"version": done_one["version"], "status_id": statuses["done"]["id"]},
    )
    assert r.status_code == 200, r.text
    others = await _assign(work, await work.ticket("Fremd"), other)
    token = await agent_token(work.admin, agent, mode="read")
    async with connect(token["secret"]) as client:
        offered = {t.name for t in (await client.list_tools()).tools}
        listed = text_of(await client.call_tool("list_my_tickets", {}))
    assert "list_my_tickets" in offered and "claim_ticket" not in offered
    assert open_one["key"] in listed
    assert done_one["key"] not in listed and others["key"] not in listed

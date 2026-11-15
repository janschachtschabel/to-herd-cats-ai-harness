"""Plan M8 task 4 (decision 11): an external agent's tokens. Whoever manages agents
issues, lists and revokes them; the token's person is the agent's responsible person,
its prefix `herd_agt_`, its clear text shown once. At `/mcp` it acts for the agent:
the agent's memberships ∩ the responsible person's rights ∩ the token's scope, read
anew at every call; while the agent rests (paused, its responsible person inactive,
without `mcp.use` or replaced) the token answers 401. What it writes is the agent's,
with the token's name as the AI mark."""

import logging
import uuid
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Unauthorized
from app.core.outbox import EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import Agent, AgentStatus
from app.modules.audit.models import AuditLog
from app.modules.spaces.models import SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.tokens.models import AccessToken
from app.modules.users.models import User
from tests.factories_external_agents import agent_token, make_external
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_tokens import bearer, mcp_on, resolver
from tests.factories_writing import Work

NOT_FOUND = "Nothing found (or not readable)."


async def _ready(work: Work) -> Agent:
    await mcp_on(work.admin)
    return await make_external(work)


async def _row(session: AsyncSession, token_id: object) -> AccessToken:
    stmt = select(AccessToken).where(AccessToken.id == uuid.UUID(str(token_id)))
    row = await session.scalar(stmt.execution_options(populate_existing=True))
    assert row is not None
    return row


async def test_an_agent_manager_issues_lists_and_revokes_its_tokens(
    work: Work, session: AsyncSession
) -> None:
    agent = await _ready(work)
    alice = work.bench.people.users["alice"]
    made = await agent_token(work.admin, agent, space_ids=[str(work.space.id)])
    assert made["secret"].startswith("herd_agt_")
    assert (made["kind"], made["agent_id"], made["mode"]) == ("agent", str(agent.id), "write")
    row = await _row(session, made["id"])
    assert row.user_id == alice.id and row.agent_id == agent.id
    assert made["secret"] not in str(row.__dict__)
    listed = (await work.admin.get(f"/api/agents/{agent.id}/tokens")).json()["items"]
    assert [t["id"] for t in listed] == [made["id"]] and "secret" not in listed[0]
    everyone = (await work.admin.get("/api/ai/mcp/tokens")).json()["items"]
    shown = next(t for t in everyone if t["id"] == made["id"])
    assert shown["agent"] == {"id": str(agent.id), "name": "Codi"}
    assert shown["user"]["id"] == str(alice.id)
    # the responsible person's own tokens are only their own
    alice_own = (await work.bench.people.alice.get("/api/tokens")).json()["items"]
    assert alice_own == []
    r = await work.bench.people.alice.delete(f"/api/tokens/{made['id']}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
    for _ in range(2):
        r = await work.admin.delete(f"/api/agents/{agent.id}/tokens/{made['id']}")
        assert r.status_code == 204, r.text
    audit = (
        await session.scalars(
            select(AuditLog)
            .where(AuditLog.target_id == uuid.UUID(made["id"]))
            .order_by(AuditLog.id)
        )
    ).all()
    assert [a.action for a in audit] == ["access_token.created", "access_token.revoked"]
    assert audit[0].details is not None and audit[0].details["agent_id"] == str(agent.id)
    assert made["secret"] not in str([a.details for a in audit])
    with pytest.raises(Unauthorized):
        await resolver(session).resolve(bearer(made))


async def test_who_may_issue_and_for_which_agent(work: Work) -> None:
    agent = await _ready(work)
    alice = work.bench.people.alice
    body = {"name": "X", "mode": "read", "expires_in_days": 1}
    for r in (
        await alice.post(f"/api/agents/{agent.id}/tokens", json=body),
        await alice.get(f"/api/agents/{agent.id}/tokens"),
        await work.admin.post(f"/api/agents/{uuid.uuid4()}/tokens", json=body),
    ):
        assert r.status_code == 404 and r.json()["error"]["code"] == "agent.not_found"
    r = await work.admin.post(f"/api/agents/{work.bench.agent.id}/tokens", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "token.agent_not_external"
    r = await work.admin.post(
        f"/api/agents/{agent.id}/tokens", json={**body, "space_ids": [str(work.private.id)]}
    )
    assert r.status_code == 422 and r.json()["error"]["code"] == "token.space_invalid"
    other = await make_external(work, name="Andere")
    made = await agent_token(work.admin, other)
    r = await work.admin.delete(f"/api/agents/{agent.id}/tokens/{made['id']}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "token.not_found"
    await mcp_on(work.admin, enabled=False)
    r = await work.admin.post(f"/api/agents/{agent.id}/tokens", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "token.responsible_without_mcp"


async def test_an_agent_with_tokens_is_paused_not_deleted(work: Work) -> None:
    agent = await _ready(work)
    await agent_token(work.admin, agent)
    r = await work.admin.request(
        "DELETE", f"/api/agents/{agent.id}", params={"version": agent.version}
    )
    assert r.status_code == 409 and r.json()["error"]["code"] == "agent.in_use"


async def test_it_reads_where_agent_person_and_scope_overlap(
    work: Work, session: AsyncSession, make_space: MakeSpace, connect: Connect
) -> None:
    """Alice reads `work.space` and `work.private`; the agent is a member of
    `work.space` and of `theirs`, which Alice does not read."""
    agent = await _ready(work)
    theirs = await make_space(SpaceKind.TEAM, name="Fremd")
    await SpaceRepository(session).set_member(
        theirs.id, Principal.agent(agent.id), SpaceRole.EDITOR
    )
    mine = await work.ticket("Gemeinsam")
    private = await new_ticket(work.admin, work.private.id, "Nur Alice")
    foreign = await new_ticket(work.admin, theirs.id, "Nur Agent")
    token = await agent_token(work.admin, agent, mode="read")
    found = await resolver(session).resolve(bearer(token))
    assert found.agent is not None and found.agent.id == agent.id
    assert found.actor.principal == Principal.user(work.bench.people.users["alice"].id)
    async with connect(token["secret"]) as client:
        texts = {
            t["key"]: await client.call_tool("read_ticket", {"key": t["key"]})
            for t in (mine, private, foreign)
        }
    assert not texts[mine["key"]].is_error
    assert text_of(texts[private["key"]]) == NOT_FOUND
    assert text_of(texts[foreign["key"]]) == NOT_FOUND
    # taken from the agent: gone at once
    await SpaceRepository(session).remove_member(work.space.id, Principal.agent(agent.id))
    async with connect(token["secret"]) as client:
        gone = await client.call_tool("read_ticket", {"key": mine["key"]})
    assert text_of(gone) == NOT_FOUND


async def test_the_agent_rests_while_it_or_its_person_may_not(
    work: Work, session: AsyncSession
) -> None:
    agent = await _ready(work)
    token = await agent_token(work.admin, agent)
    alice = work.bench.people.users["alice"]
    admin = work.bench.people.users["admin"]
    assert (await resolver(session).resolve(bearer(token))).agent is not None

    async def refused() -> None:
        with pytest.raises(Unauthorized):
            await resolver(session).resolve(bearer(token))

    await session.execute(update(Agent).where(Agent.id == agent.id).values(status="paused"))
    await refused()
    await session.execute(update(Agent).where(Agent.id == agent.id).values(status="active"))
    await session.execute(update(User).where(User.id == alice.id).values(is_active=False))
    await refused()
    await session.execute(update(User).where(User.id == alice.id).values(is_active=True))
    r = await work.admin.put(
        f"/api/ai/assignments/users/{alice.id}", json={"no_ai": True, "version": None}
    )
    assert r.status_code == 200, r.text
    await refused()
    await work.admin.delete(f"/api/ai/assignments/users/{alice.id}", params={"version": 1})
    assert (await resolver(session).resolve(bearer(token))).agent is not None
    await session.execute(
        update(Agent).where(Agent.id == agent.id).values(responsible_user_id=admin.id)
    )
    await refused()  # someone else answers for it now: issue a new token
    await session.execute(
        update(Agent).where(Agent.id == agent.id).values(responsible_user_id=alice.id)
    )
    await mcp_on(work.admin, enabled=False)
    await refused()
    assert AgentStatus.ACTIVE == (await session.get(Agent, agent.id)).status  # type: ignore[union-attr]


async def test_what_it_writes_is_the_agents_with_the_tokens_name(
    work: Work, connect: Connect
) -> None:
    agent = await _ready(work)
    ticket = await work.ticket("Schreiben")
    token = await agent_token(work.admin, agent, space_ids=[str(work.space.id)])
    async with connect(token["secret"]) as client:
        offered = {t.name for t in (await client.list_tools()).tools}
        commented = await client.call_tool(
            "comment_ticket", {"key": ticket["key"], "text": "Ich schaue es mir an."}
        )
        made = await client.call_tool(
            "create_ticket", {"space_id": str(work.space.id), "title": "Vom Agenten"}
        )
    assert {"list_my_tickets", "claim_ticket", "comment_ticket"} <= offered
    assert not {"update_page", "post_message", "assign_ticket"} & offered
    assert not commented.is_error and not made.is_error, text_of(made)
    thread = (await work.admin.get(f"/api/tickets/{ticket['number']}/thread")).json()
    messages = (await work.admin.get(f"/api/conversations/{thread['id']}/messages")).json()
    (comment,) = [m for m in messages["items"] if m["kind"] != "system"]
    assert comment["kind"] == "agent"
    assert comment["author"]["type"] == "agent" and comment["author"]["id"] == str(agent.id)
    assert comment["via_token"] == "Codex"
    number = int(text_of(made).split("HC-")[1].rstrip("."))
    created: dict[str, Any] = (await work.admin.get(f"/api/tickets/{number}")).json()
    assert created["reporter"] == {"type": "agent", "id": str(agent.id), "name": "Codi"}
    assert created["via_token"] == "Codex"


async def test_a_viewer_agent_writes_nothing_even_with_a_write_token(
    work: Work, connect: Connect, session: AsyncSession
) -> None:
    """Alice edits there; the agent only views: its role caps hers."""
    agent = await _ready(work)
    await SpaceRepository(session).set_member(
        work.space.id, Principal.agent(agent.id), SpaceRole.VIEWER
    )
    ticket = await work.ticket("Nur lesen")
    token = await agent_token(work.admin, agent)
    statuses = (await work.admin.get(f"/api/spaces/{work.space.id}/ticket-statuses")).json()
    active = next(s for s in statuses["items"] if s["category"] == "active")
    async with connect(token["secret"]) as client:
        moved = await client.call_tool(
            "set_ticket_status", {"key": ticket["key"], "status": active["name"]}
        )
        claimed = await client.call_tool("claim_ticket", {"key": ticket["key"]})
    assert moved.is_error and claimed.is_error
    shown = (await work.admin.get(f"/api/tickets/{ticket['number']}")).json()
    assert shown["assignee"] is None and shown["status"]["category"] == "open"


async def test_no_agent_token_value_leaks_anywhere(
    work: Work,
    session: AsyncSession,
    connect: Connect,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    agent = await _ready(work)
    ticket = await work.ticket("Geheim")
    made = await agent_token(work.admin, agent)
    await work.admin.get(f"/api/agents/{agent.id}/tokens")
    async with connect(made["secret"]) as client:
        await client.call_tool("claim_ticket", {"key": ticket["key"]})
        await client.call_tool("comment_ticket", {"key": ticket["key"], "text": "Hallo"})
    await work.admin.delete(f"/api/agents/{agent.id}/tokens/{made['id']}")
    errors = []
    try:
        await resolver(session).resolve(bearer(made))
    except AppError as refused:
        errors.append(f"{refused.code} {refused.message} {refused.details}")
    row = await _row(session, made["id"])
    audit = [
        f"{e.action} {e.details} {e.target_id}" for e in await session.scalars(select(AuditLog))
    ]
    outbox = [f"{e.type} {e.payload}" for e in await session.scalars(select(EventOutbox))]
    logged = capsys.readouterr()
    records = [str(r.__dict__) for r in caplog.records]
    haystack = "\n".join([*audit, *outbox, *errors, *records, logged.out, logged.err])
    assert "access_token.created" in haystack and "mcp.tool_call" in haystack
    for value in (made["secret"], row.token_hash.hex()):
        assert value not in haystack
        assert value[-20:] not in haystack


async def test_a_change_of_responsibility_revokes_the_agents_tokens(
    work: Work, session: AsyncSession
) -> None:
    """Module review M8 1, finding 9: the tokens of the first responsible person came
    back to life when responsibility returned to them. They are revoked at the change."""
    agent = await _ready(work)
    token = await agent_token(work.admin, agent)
    alice = work.bench.people.users["alice"]
    admin = work.bench.people.users["admin"]
    await mcp_on(work.admin)
    url = f"/api/agents/{agent.id}"
    version = (await work.admin.get(url)).json()["version"]
    r = await work.admin.patch(url, json={"responsible_user_id": str(admin.id), "version": version})
    assert r.status_code == 200, r.text
    r = await work.admin.patch(
        url, json={"responsible_user_id": str(alice.id), "version": r.json()["version"]}
    )
    assert r.status_code == 200, r.text
    with pytest.raises(Unauthorized):
        await resolver(session).resolve(bearer(token))
    revoked = await session.scalars(select(AccessToken).where(AccessToken.agent_id == agent.id))
    assert all(t.revoked_at is not None for t in revoked)
    audit = await session.scalar(
        select(AuditLog).where(AuditLog.action == "agent.updated").order_by(AuditLog.id).limit(1)
    )
    assert audit is not None and audit.details["tokens_revoked"] == 1

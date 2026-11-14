"""Plan M6 task 8: a ticket assigned to an agent starts its run in the ticket's thread,
asked by whoever assigned it, with the ticket as its task; its answer is a comment
there. A run that cannot start or that stops leaves the ticket assigned, says why in
the thread and tells the agent's responsible person. One run per ticket. An agent
hands a ticket over to another agent for the same person, at most three times."""

import uuid
from typing import Any

from sqlalchemy import func, select, update

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import Agent, AgentStatus, Run, StopReason
from app.modules.messaging.models import Conversation, ConversationKind, Message
from app.modules.spaces.repository import SpaceRepository
from app.modules.tickets.models import WorkItem
from tests.factories_agents import make_agent
from tests.factories_messaging import post
from tests.factories_spaces import personal_space_of
from tests.factories_tickets import new_ticket, status_of
from tests.factories_tools import call
from tests.factories_writing import Work, set_level


async def _assign(work: Work, ticket: dict[str, Any], agent: Agent) -> dict[str, Any]:
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}",
        json={"version": ticket["version"], "assignee": {"type": "agent", "id": str(agent.id)}},
    )
    assert r.status_code == 200, r.text
    changed: dict[str, Any] = r.json()
    return changed


async def _thread(work: Work, ticket: dict[str, Any]) -> list[dict[str, Any]]:
    """The ticket thread's top-level messages, oldest first."""
    thread = (await work.admin.get(f"/api/tickets/{ticket['number']}/thread")).json()
    r = await work.admin.get(f"/api/conversations/{thread['id']}/messages?limit=100")
    assert r.status_code == 200, r.text
    return sorted(r.json()["items"], key=lambda m: m["id"])


def _entries(messages: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [m["system"] for m in messages if m["kind"] == "system" and m["system"]["key"] == key]


async def _runs(work: Work, agent: Agent) -> list[Run]:
    stmt = select(Run).where(Run.agent_id == agent.id).order_by(Run.created_at)
    return list(
        (await work.bench.session.scalars(stmt.execution_options(populate_existing=True))).all()
    )


async def _activity(work: Work, who: str = "admin") -> list[tuple[str, str]]:
    items = (await getattr(work.bench.people, who).get("/api/activity")).json()["items"]
    return [(a["reason"], a["message_id"]) for a in items]


async def _said_in(work: Work, *kinds: ConversationKind) -> int:
    stmt = (
        select(func.count())
        .select_from(Message)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .where(Conversation.kind.in_(kinds))
    )
    return int(await work.bench.session.scalar(stmt) or 0)


async def _bert(work: Work, role: SpaceRole = SpaceRole.EDITOR) -> Agent:
    bench = work.bench
    bert = await make_agent(bench.session, bench.people, bench.connection.id, name="Bert")
    await SpaceRepository(bench.session).set_member(work.space.id, Principal.agent(bert.id), role)
    return bert


async def test_a_ticket_for_a_level_2_agent_ends_in_review_with_a_comment(work: Work) -> None:
    """Acceptance (plan M6 task 8): nothing about the ticket reaches a channel or a DM."""
    bench = work.bench
    channel = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "c"})
    await post(work.admin, channel.json()["id"], "Guten Morgen.")
    bench.stub.state.replies.append({"content": "Hallo Alice."})
    await bench.say("Hallo Ava")  # Alice's DM with the agent
    assert await bench.run_next() == StopReason.COMPLETED
    quiet = await _said_in(work, ConversationKind.CHANNEL, ConversationKind.DM)
    ticket = await work.ticket("Inventur vorbereiten")
    key = f"HC-{ticket['number']}"
    assert bench.agent.level == 2
    await _assign(work, ticket, bench.agent)
    (run,) = [r for r in await _runs(work, bench.agent) if r.work_item_id is not None]
    row = await bench.session.scalar(select(WorkItem).where(WorkItem.number == ticket["number"]))
    assert row is not None
    assert (run.trigger_message_id, run.work_item_id, run.chain_depth) == (None, row.id, 0)
    assert run.user_id == bench.people.users["admin"].id
    review = await status_of(work.admin, work.space.id, "review")
    bench.stub.state.replies.extend(
        [call("set_ticket_status", key=key, status=review["name"]), {"content": "Bitte prüfen."}]
    )
    assert await bench.run_next() == StopReason.COMPLETED
    assert key in bench.stub.state.texts()
    shown = (await work.admin.get(f"/api/tickets/{ticket['number']}")).json()
    assert shown["status"]["category"] == "review"
    comments = [m for m in await _thread(work, ticket) if m["kind"] == "agent"]
    assert [(m["body_md"], m["run_id"]) for m in comments] == [("Bitte prüfen.", str(run.id))]
    assert await _said_in(work, ConversationKind.CHANNEL, ConversationKind.DM) == quiet
    seen = (await work.admin.get(f"/api/runs/{run.id}")).json()
    assert seen["trigger_message_id"] is None and seen["place"]["kind"] == "thread_ticket"


async def test_an_assignment_that_cannot_start_says_why(work: Work) -> None:
    bench = work.bench
    bench.agent.status = AgentStatus.PAUSED
    await bench.session.flush()
    ticket = await work.ticket()
    changed = await _assign(work, ticket, bench.agent)
    assert changed["assignee"]["id"] == str(bench.agent.id)  # it stays assigned
    assert await _runs(work, bench.agent) == []
    messages = await _thread(work, ticket)
    (entry,) = _entries(messages, "run.refused")
    assert entry["actor"] == {"id": str(bench.agent.id), "name": "Ava", "type": "agent"}
    assert entry["new"]["value"] == "agent.paused"
    (notice,) = [m for m in messages if m["kind"] == "system" and m["system"] == entry]
    assert ("run_stopped", notice["id"]) in await _activity(work)  # the responsible person


async def test_one_run_per_ticket(work: Work) -> None:
    bench = work.bench
    ticket = await work.ticket()
    await _assign(work, ticket, bench.agent)
    thread = (await work.admin.get(f"/api/tickets/{ticket['number']}/thread")).json()
    body = {"body_md": "@Ava schneller", "mentions": [str(bench.agent.id)]}
    r = await work.admin.post(f"/api/conversations/{thread['id']}/messages", json=body)
    assert r.json()["agent_run"]["reason"] == "run.waiting"
    bert = await _bert(work)
    fresh = (await work.admin.get(f"/api/tickets/{ticket['number']}")).json()
    await _assign(work, fresh, bert)
    assert await _runs(work, bert) == []
    (entry,) = _entries(await _thread(work, ticket), "run.refused")
    assert entry["new"]["value"] == "run.waiting" and entry["actor"]["name"] == "Bert"


async def test_a_ticket_run_that_stops_tells_the_responsible_person(work: Work) -> None:
    bench = work.bench
    ticket = await work.ticket()
    await _assign(work, ticket, bench.agent)
    bench.stub.state.failures.append(401)
    assert await bench.run_next() == StopReason.PROVIDER_REFUSED
    messages = await _thread(work, ticket)
    (entry,) = _entries(messages, "run.stopped")
    assert entry["new"]["value"] == "provider_refused"
    (notice,) = [m for m in messages if m["kind"] == "system" and m["system"] == entry]
    assert notice["parent_id"] is None
    assert entry["actor"] == {"id": str(bench.agent.id), "name": "Ava", "type": "agent"}
    assert ("run_stopped", notice["id"]) in await _activity(work)
    items = (await work.admin.get("/api/activity")).json()["items"]
    (item,) = [a for a in items if a["reason"] == "run_stopped"]
    assert item["author"] == {"type": "agent", "id": str(bench.agent.id), "name": "Ava"}
    assert item["snippet"] == "" and item["conversation"]["kind"] == "thread_ticket"


async def _handing(work: Work) -> tuple[dict[str, Any], Agent, Run]:
    """Ava (level 3, a moderator: she may assign) has a ticket; Bert edits there."""
    bench = work.bench
    await set_level(bench, 3)
    await bench.join(work.space, SpaceRole.MODERATOR)
    bert = await _bert(work)
    ticket = await work.ticket()
    await _assign(work, ticket, bench.agent)
    (run,) = await _runs(work, bench.agent)
    hand = call(
        "assign_ticket",
        key=f"HC-{ticket['number']}",
        assignee_type="agent",
        assignee_id=str(bert.id),
        reason="Bert kennt das Lager.",
    )
    bench.stub.state.replies.extend([hand, {"content": "Übergeben."}])
    return ticket, bert, run


async def test_a_handover_starts_the_next_agents_run_for_the_same_person(work: Work) -> None:
    bench = work.bench
    ticket, bert, first = await _handing(work)
    assert await bench.run_next() == StopReason.COMPLETED
    (second,) = await _runs(work, bert)
    assert (second.user_id, second.chain_depth) == (first.user_id, 1)
    assert (second.work_item_id, second.conversation_id) == (
        first.work_item_id,
        first.conversation_id,
    )
    bench.stub.state.replies.append({"content": "Ich übernehme."})
    assert await bench.run_next() == StopReason.COMPLETED
    comments = [m["body_md"] for m in await _thread(work, ticket) if m["kind"] == "agent"]
    assert comments == ["Bert kennt das Lager.", "Übergeben.", "Ich übernehme."]
    shown = (await work.admin.get(f"/api/runs/{second.id}")).json()
    assert shown["chain_depth"] == 1


async def test_the_fourth_handover_is_refused(work: Work) -> None:
    bench = work.bench
    ticket, bert, first = await _handing(work)
    await bench.session.execute(update(Run).where(Run.id == first.id).values(chain_depth=3))
    assert await bench.run_next() == StopReason.COMPLETED
    assert "Refused (run.handover_limit)." in bench.stub.state.texts()
    assert await _runs(work, bert) == []
    shown = (await work.admin.get(f"/api/tickets/{ticket['number']}")).json()
    assert shown["assignee"]["id"] == str(bench.agent.id)
    (entry,) = _entries(await _thread(work, ticket), "run.refused")
    assert entry["new"]["value"] == "run.handover_limit" and entry["actor"]["name"] == "Ava"
    assert uuid.UUID(entry["actor"]["id"]) == bench.agent.id


async def _pia(work: Work) -> Agent:
    """Alice's personal agent, made a member of the team space behind the API's back
    (it never is through it): only Alice may still hand it tickets."""
    r = await work.bench.people.alice.post(
        "/api/agents", json={"name": "Pia", "personal": True, "status": "active"}
    )
    assert r.status_code == 201, r.text
    pia = await work.bench.session.get(Agent, uuid.UUID(r.json()["id"]))
    assert pia is not None
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.agent(pia.id), SpaceRole.EDITOR
    )
    return pia


async def test_only_its_owner_hands_tickets_to_a_personal_agent(work: Work) -> None:
    pia = await _pia(work)
    ticket = await work.ticket()
    body = {"version": ticket["version"], "assignee": {"type": "agent", "id": str(pia.id)}}
    r = await work.admin.patch(f"/api/tickets/{ticket['number']}", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "ticket.assignee_invalid"
    personal = await personal_space_of(work.bench.session, work.bench.people.users["alice"])
    own = await new_ticket(work.bench.people.alice, personal.id, "Meins")
    r = await work.bench.people.alice.patch(
        f"/api/tickets/{own['number']}",
        json={"version": own["version"], "assignee": {"type": "agent", "id": str(pia.id)}},
    )
    assert r.status_code == 200, r.text
    (run,) = await _runs(work, pia)
    assert run.user_id == work.bench.people.users["alice"].id


async def test_no_handover_to_someone_elses_personal_agent(work: Work) -> None:
    bench = work.bench
    await set_level(bench, 3)
    await bench.join(work.space, SpaceRole.MODERATOR)
    pia = await _pia(work)
    ticket = await work.ticket()
    await _assign(work, ticket, bench.agent)  # the admin asks Ava
    hand = call(
        "assign_ticket",
        key=f"HC-{ticket['number']}",
        assignee_type="agent",
        assignee_id=str(pia.id),
        reason="Pia?",
    )
    bench.stub.state.replies.extend([hand, {"content": "Nicht möglich."}])
    assert await bench.run_next() == StopReason.COMPLETED
    assert "Refused (ticket.assignee_invalid)." in bench.stub.state.texts()
    assert await _runs(work, pia) == []

"""Plan M6 task 6: the tickets' writing tools. Each changes a ticket through the ticket
service with the run's actor, written for the agent: its comments are agent messages
in the ticket's thread with the run, its changes are events whose actor is the agent
(the run named), and the timeline names the agent. An agent sets a status of category
`review` at most, assigns with a reason in the thread, and finds nothing AI may not
read."""

import uuid

import pytest
from sqlalchemy import select

from app.core.outbox import Event, EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal, PrincipalType
from app.modules.agents.toolbox import ticket_tools
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.agents.toolbox.catalog import CATALOG
from app.modules.ai.models import AiPolicy
from app.modules.messaging.models import Conversation, MessageKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.tickets.handlers import ticket_timeline
from app.modules.tickets.models import TicketPageLink, WorkItem
from tests.factories_agents import make_agent
from tests.factories_tickets import status_of
from tests.factories_tools import tool_context
from tests.factories_writing import Work, events, messages_in


async def _row(work: Work, number: int) -> WorkItem:
    row = await work.bench.session.scalar(
        select(WorkItem).where(WorkItem.number == number).execution_options(populate_existing=True)
    )
    assert row is not None
    return row


async def _thread(work: Work, ticket_id: uuid.UUID) -> Conversation:
    thread = await work.bench.session.scalar(
        select(Conversation).where(Conversation.work_item_id == ticket_id)
    )
    assert thread is not None
    return thread


def _key(ticket: dict[str, object]) -> str:
    return f"HC-{ticket['number']}"


async def test_a_comment_is_the_agents_message_in_the_tickets_thread(work: Work) -> None:
    ticket = await work.ticket()
    ctx = await tool_context(work.bench)
    args = ticket_tools.CommentTicketArgs(key=_key(ticket), text="Ich schaue es mir an.")
    assert (await ticket_tools.comment_ticket(ctx, args)).text == f"Commented on {_key(ticket)}."
    row = await _row(work, int(str(ticket["number"])))
    found = [m for m in await messages_in(work.bench.session, (await _thread(work, row.id)).id)]
    comments = [m for m in found if m.kind == MessageKind.AGENT]
    assert len(comments) == 1
    comment = comments[0]
    assert (comment.author_type, comment.author_id, comment.run_id) == (
        "agent",
        work.bench.agent.id,
        ctx.run.id,
    )
    assert comment.body_md == "Ich schaue es mir an." and comment.parent_id is None
    r = await work.bench.people.alice.get(f"/api/conversations/{comment.conversation_id}/messages")
    shown = next(m for m in r.json()["items"] if m["id"] == str(comment.id))
    assert shown["author"]["type"] == "agent" and shown["author"]["name"] == "Ava"
    assert (shown["kind"], shown["run_id"]) == ("agent", str(ctx.run.id))


async def test_the_status_goes_to_review_at_most(work: Work) -> None:
    ticket = await work.ticket()
    review = await status_of(work.admin, work.space.id, "review")
    ctx = await tool_context(work.bench)
    done = await status_of(work.admin, work.space.id, "done")
    cancelled = await status_of(work.admin, work.space.id, "cancelled")
    for status in (done, cancelled):
        args = ticket_tools.SetTicketStatusArgs(key=_key(ticket), status=status["name"])
        refused = await ticket_tools.set_ticket_status(ctx, args)
        assert refused.text.startswith("Only a person sets a status of category done")
        assert repr(review["name"]) in refused.text
    unknown = ticket_tools.SetTicketStatusArgs(key=_key(ticket), status="Irgendwas")
    assert "Not a status" in (await ticket_tools.set_ticket_status(ctx, unknown)).text
    args = ticket_tools.SetTicketStatusArgs(key=_key(ticket), status=review["name"].upper())
    result = await ticket_tools.set_ticket_status(ctx, args)
    assert result.text == f"{_key(ticket)} is now {review['name']!r}."
    row = await _row(work, int(str(ticket["number"])))
    assert str(row.status_id) == review["id"]
    (event,) = [
        e for e in await events(work.bench.session, "ticket.updated") if e.subject_id == row.id
    ]
    assert (event.actor_type, event.actor_id) == (PrincipalType.AGENT, work.bench.agent.id)
    assert event.payload["run_id"] == str(ctx.run.id)
    assert event.payload["changes"]["status"]["to"] == review["id"]


async def test_the_timeline_names_the_agent_and_its_run(work: Work) -> None:
    ticket = await work.ticket()
    review = await status_of(work.admin, work.space.id, "review")
    ctx = await tool_context(work.bench)
    args = ticket_tools.SetTicketStatusArgs(key=_key(ticket), status=review["name"])
    await ticket_tools.set_ticket_status(ctx, args)
    row = await _row(work, int(str(ticket["number"])))
    for event in await events(work.bench.session, "ticket.updated"):
        await ticket_timeline(work.bench.session, Event.of(event))
    thread = await _thread(work, row.id)
    r = await work.bench.people.alice.get(f"/api/conversations/{thread.id}/messages")
    entry = next(m["system"] for m in r.json()["items"] if m["kind"] == "system")
    assert entry["key"] == "ticket.status_changed"
    assert entry["actor"] == {"id": str(work.bench.agent.id), "name": "Ava", "type": "agent"}
    assert entry["run_id"] == str(ctx.run.id)


async def test_a_created_ticket_is_reported_by_the_agent(work: Work) -> None:
    ctx = await tool_context(work.bench)
    args = ticket_tools.CreateTicketArgs(
        space_id=work.space.id, title="Neu vom Agenten", description_md="Bitte prüfen."
    )
    result = await ticket_tools.create_ticket(ctx, args)
    assert result.text.startswith("Created HC-")
    number = int(result.text.removeprefix("Created HC-").rstrip("."))
    row = await _row(work, number)
    assert (row.reporter_type, row.reporter_id) == ("agent", work.bench.agent.id)
    r = await work.bench.people.alice.get(f"/api/tickets/{number}")
    assert r.json()["reporter"] == {"type": "agent", "id": str(work.bench.agent.id), "name": "Ava"}
    (event,) = await events(work.bench.session, "ticket.created")
    assert (event.actor_type, event.payload["run_id"]) == (PrincipalType.AGENT, str(ctx.run.id))


async def test_a_ticket_ai_may_not_read_is_not_there(work: Work) -> None:
    ticket = await work.ticket()
    work.space.ai_policy = AiPolicy.NONE
    await work.bench.session.flush()
    ctx = await tool_context(work.bench)
    comment = ticket_tools.CommentTicketArgs(key=_key(ticket), text="x")
    assert (await ticket_tools.comment_ticket(ctx, comment)).text == NOT_FOUND
    status = ticket_tools.SetTicketStatusArgs(key=_key(ticket), status="x")
    assert (await ticket_tools.set_ticket_status(ctx, status)).text == NOT_FOUND
    create = ticket_tools.CreateTicketArgs(space_id=work.space.id, title="t")
    assert (await ticket_tools.create_ticket(ctx, create)).text == NOT_FOUND
    hidden = ticket_tools.CommentTicketArgs(key="HC-99999", text="x")
    assert (await ticket_tools.comment_ticket(ctx, hidden)).text == NOT_FOUND


async def test_a_page_is_linked_once(work: Work) -> None:
    ticket = await work.ticket()
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    args = ticket_tools.LinkTicketPageArgs(key=_key(ticket), page_id=uuid.UUID(page_id))
    assert (await ticket_tools.link_ticket_page(ctx, args)).text.startswith("Linked")
    assert (await ticket_tools.link_ticket_page(ctx, args)).text.startswith("Already linked")
    links = (await work.bench.session.scalars(select(TicketPageLink))).all()
    assert [str(link.page_id) for link in links] == [page_id]
    (event,) = await events(work.bench.session, "ticket.updated")
    assert event.actor_type == PrincipalType.AGENT


async def test_assigning_hands_over_with_the_reason_in_the_thread(work: Work) -> None:
    ticket = await work.ticket()
    alice = work.bench.people.users["alice"]
    ctx = await tool_context(work.bench)
    args = ticket_tools.AssignTicketArgs(
        key=_key(ticket), assignee_type="user", assignee_id=alice.id, reason="Alice kennt es."
    )
    assert (await ticket_tools.assign_ticket(ctx, args)).text == f"Assigned {_key(ticket)}."
    row = await _row(work, int(str(ticket["number"])))
    assert (row.assignee_type, row.assignee_id) == ("user", alice.id)
    thread = await _thread(work, row.id)
    (comment,) = [m for m in await messages_in(work.bench.session, thread.id) if m.kind == "agent"]
    assert comment.body_md == "Alice kennt es." and comment.run_id == ctx.run.id


@pytest.mark.parametrize("role", [SpaceRole.EDITOR, SpaceRole.VIEWER, None])
async def test_an_agent_takes_tickets_only_as_an_editor_of_the_space(
    work: Work, role: SpaceRole | None
) -> None:
    bench = work.bench
    spaces = SpaceRepository(bench.session)
    alice = bench.people.users["alice"]
    await spaces.set_member(work.space.id, Principal.user(alice.id), SpaceRole.MODERATOR)
    await bench.join(work.space, SpaceRole.MODERATOR)  # the run: Alice held to Ava's role
    other = await make_agent(bench.session, bench.people, bench.connection.id, name="Bo")
    if role is not None:
        await spaces.set_member(work.space.id, Principal.agent(other.id), role)
    ticket = await work.ticket()
    ctx = await tool_context(bench)
    args = ticket_tools.AssignTicketArgs(
        key=_key(ticket), assignee_type="agent", assignee_id=other.id, reason="Bo übernimmt."
    )
    result = await ticket_tools.assign_ticket(ctx, args)
    row = await _row(work, int(str(ticket["number"])))
    thread = await _thread(work, row.id)
    comments = [m for m in await messages_in(bench.session, thread.id) if m.kind == "agent"]
    if role == SpaceRole.EDITOR:
        assert result.text == f"Assigned {_key(ticket)}."
        assert (row.assignee_type, row.assignee_id) == ("agent", other.id)
        assert [c.body_md for c in comments] == ["Bo übernimmt."]
    else:
        assert result.text == "Refused (ticket.assignee_invalid)."
        assert row.assignee_id is None and comments == []  # the savepoint took it all back


async def test_assigning_someone_else_needs_the_right_to_assign(work: Work) -> None:
    ticket = await work.ticket()
    ctx = await tool_context(work.bench)  # Alice is an editor: no ticket.assign
    bob = work.bench.people.users["admin"]
    args = ticket_tools.AssignTicketArgs(
        key=_key(ticket), assignee_type="user", assignee_id=bob.id, reason="r"
    )
    assert (await ticket_tools.assign_ticket(ctx, args)).text == (
        "Not allowed (auth.permission_denied)."
    )


def test_no_tool_deletes_trashes_or_decides_proposals() -> None:
    forbidden = ("delete", "trash", "purge", "remove", "accept", "reject", "withdraw")
    assert not [name for name in CATALOG if any(word in name for word in forbidden)]


async def test_an_assignment_event_names_an_agent_assignee(work: Work) -> None:
    """A person hands a ticket to an agent over the API (ai.use, ticket.assign)."""
    ticket = await work.ticket()
    r = await work.admin.patch(
        f"/api/tickets/{ticket['number']}",
        json={
            "version": ticket["version"],
            "assignee": {"type": "agent", "id": str(work.bench.agent.id)},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["assignee"] == {"type": "agent", "id": str(work.bench.agent.id), "name": "Ava"}
    rows = (await work.bench.session.scalars(select(EventOutbox))).all()
    assert any(
        e.payload.get("changes", {}).get("assignee", {}).get("to") == str(work.bench.agent.id)
        for e in rows
    )

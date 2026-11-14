"""Event rules (plan M7 task 5, decisions 8 and 9): an event of the rule's kind in the
space of its place starts a run of its owner at its place, told only the event's
kind and the ids of what it is about (framed as untrusted); within the quiet time at
most one run: further events are counted, and the run at the quiet time's end is
told how many. An event handed over again starts nothing more; filters (tag, kind)
are read on the ticket as it is; an event of another space or organisation starts
nothing."""

import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select

from app.core.outbox import Event
from app.modules.agents.models import RunState, StopReason
from app.modules.automations import runs as automation_runs
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.event_rules import on_event
from app.modules.automations.firing import fire_next
from app.modules.automations.models import FiringOutcome
from app.modules.wiki.events import PAGE_REVIEW_DUE, page_event
from app.modules.wiki.models import Page
from tests.factories_agents import Bench
from tests.factories_automations import T0, finish_runs, firings, reload, ruled, runs_of
from tests.factories_writing import Work, events, messages_in
from tests.test_access import actor_of
from tests.test_wiki_attachments import PNG, _uploaded

QUIET = 300


async def _channel(work: Work, name: str = "eingang") -> uuid.UUID:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": name})
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


async def take_in(bench: Bench, type_: str, at: Any, index: int = -1) -> Event:
    """Hand the event (the newest of its kind by default) to the rules."""
    event = Event.of((await events(bench.session, type_))[index])
    await on_event(bench.session, event, at)
    return event


def _first_turn(bench: Bench) -> str:
    body = next(r.body for r in reversed(bench.stub.state.log) if r.path.endswith("/completions"))
    return str(next(m for m in body["messages"] if m["role"] == "user")["content"])


async def test_a_ticket_created_in_the_space_starts_its_owners_run(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    rule = await ruled(bench, channel, instruction="Ordne neue Tickets ein.")
    made = await work.ticket("Drucker GEHEIM-TITEL")  # created by the admin
    await take_in(bench, "ticket.created", T0)
    [run] = await runs_of(bench.session, rule.id)
    alice = bench.people.users["alice"]
    assert (run.user_id, run.conversation_id, run.chain_depth) == (alice.id, channel, 0)
    [logged] = await firings(bench.session, rule.id)
    assert (logged.outcome, logged.run_id, logged.due_at) == ("started", run.id, T0)
    after = await reload(bench.session, rule.id)
    assert (after.quiet_until, after.next_due_at) == (T0 + timedelta(seconds=QUIET), None)
    bench.stub.state.replies.append({"content": "Eingeordnet."})
    assert await bench.run_next() == StopReason.COMPLETED
    turn = _first_turn(bench)
    assert turn.startswith("Ordne neue Tickets ein.")
    assert '<untrusted source="event" type="ticket.created">' in turn
    assert f"key: HC-{made['number']}" in turn and f"ticket_id: {made['id']}" in turn
    assert "GEHEIM" not in turn  # ids only: the run reads the ticket with its tools
    said = await messages_in(bench.session, channel)
    (root,) = [m for m in said if m.parent_id is None]
    assert json.loads(root.body_md)["automation_id"] == str(rule.id)


async def test_an_event_handed_over_again_starts_no_second_run(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    rule = await ruled(bench, channel)
    await work.ticket()
    await take_in(bench, "ticket.created", T0)
    await take_in(bench, "ticket.created", T0 + timedelta(seconds=QUIET + 1))  # again
    assert len(await runs_of(bench.session, rule.id)) == 1
    assert len(await firings(bench.session, rule.id)) == 1
    taken = await bench.session.scalars(select(AutomationEvent))
    assert len(list(taken)) == 1


async def test_events_within_the_quiet_time_count_for_one_later_run(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    rule = await ruled(bench, channel)
    await work.ticket("Erstes")
    await take_in(bench, "ticket.created", T0)
    await finish_runs(bench.session)
    later = []
    for second in (10, 20, 30):
        later.append(await work.ticket(f"Später {second}"))
        await take_in(bench, "ticket.created", T0 + timedelta(seconds=second))
    assert len(await runs_of(bench.session, rule.id)) == 1  # no run within the quiet time
    end = T0 + timedelta(seconds=QUIET)
    assert (await reload(bench.session, rule.id)).next_due_at == end
    assert await fire_next(bench.session, end - timedelta(seconds=1)) is None
    fired = await fire_next(bench.session, end)
    assert fired is not None and fired.outcome == FiringOutcome.STARTED
    after = await reload(bench.session, rule.id)
    assert (after.next_due_at, after.quiet_until) == (None, end + timedelta(seconds=QUIET))
    assert await fire_next(bench.session, end + timedelta(hours=1)) is None  # once only
    bench.stub.state.replies.append({"content": "Drei neue."})
    assert await bench.run_next() == StopReason.COMPLETED
    turn = _first_turn(bench)
    assert "events: 3" in turn
    for ticket in later:
        assert f"ticket_id: {ticket['id']}" in turn
    assert len(await firings(bench.session, rule.id)) == 2


async def test_a_new_event_after_the_quiet_time_takes_the_waiting_ones_along(
    work: Work,
) -> None:
    bench, channel = work.bench, await _channel(work)
    rule = await ruled(bench, channel)
    for second in (0, 10):
        await work.ticket(f"T{second}")
        await take_in(bench, "ticket.created", T0 + timedelta(seconds=second))
    await finish_runs(bench.session)
    await work.ticket("Spät")
    await take_in(bench, "ticket.created", T0 + timedelta(seconds=QUIET + 5))  # loop was late
    assert len(await runs_of(bench.session, rule.id)) == 2
    after = await reload(bench.session, rule.id)
    assert after.next_due_at is None
    waiting = await bench.session.scalars(
        select(AutomationEvent).where(AutomationEvent.firing_id.is_(None))
    )
    assert list(waiting) == []


async def test_filters_read_the_tickets_tag_and_kind(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    tag = (await work.admin.post("/api/tags", json={"name": "Kunde"})).json()
    rule = await ruled(bench, channel, tag_id=uuid.UUID(tag["id"]), ticket_kind="bug")
    at = T0
    for kind, tagged in (("task", True), ("bug", False), ("bug", True)):
        made = await work.ticket(kind=kind)
        if tagged:
            r = await work.admin.put(
                f"/api/tickets/{made['number']}/tags",
                json={"tag_ids": [tag["id"]], "version": made["version"]},
            )
            assert r.status_code == 200, r.text
        await take_in(bench, "ticket.created", at)
        at += timedelta(seconds=QUIET + 1)
    [run] = await runs_of(bench.session, rule.id)
    [logged] = await firings(bench.session, rule.id)
    assert logged.run_id == run.id
    assert len(list(await bench.session.scalars(select(AutomationEvent)))) == 1


async def test_an_event_of_another_space_or_organisation_starts_nothing(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    rule = await ruled(bench, channel)
    elsewhere = await work.ticket()
    r = await work.admin.post(f"/api/spaces/{work.private.id}/tickets", json={"title": "Fremd"})
    assert r.status_code == 201, r.text
    await take_in(bench, "ticket.created", T0)  # in the other space
    event = Event.of((await events(bench.session, "ticket.created"))[0])
    foreign = Event(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        type=event.type,
        actor=event.actor,
        space_id=event.space_id,
        subject_type="ticket",
        subject_id=uuid.UUID(elsewhere["id"]),
        payload=event.payload,
        created_at=event.created_at,
    )
    await on_event(bench.session, foreign, T0)
    assert await runs_of(bench.session, rule.id) == []
    assert await firings(bench.session, rule.id) == []


async def test_pages_attachments_and_due_reviews_start_runs(work: Work) -> None:
    bench = work.bench
    rules = {
        kind: await ruled(bench, await _channel(work, kind.replace(".", "-")), kind)
        for kind in ("page.published", "attachment.uploaded", "page.review_due")
    }
    page_id = await work.page()
    await take_in(bench, "page.published", T0)
    made = await _uploaded(work.admin, {"id": page_id}, "plan.png", PNG)
    await take_in(bench, "attachment.uploaded", T0)
    page = await bench.session.get(Page, uuid.UUID(page_id))
    assert page is not None
    admin = await actor_of(bench.session, bench.people.users["admin"])
    await page_event(bench.session, admin, PAGE_REVIEW_DUE, page)
    await take_in(bench, PAGE_REVIEW_DUE, T0)
    for rule in rules.values():
        [run] = await runs_of(bench.session, rule.id)
        assert run.state == RunState.QUEUED
    taken = {
        str(row.automation_id): row.ids
        for row in await bench.session.scalars(select(AutomationEvent))
    }
    assert taken[str(rules["page.published"].id)] == {"page_id": page_id}
    assert taken[str(rules["attachment.uploaded"].id)] == {
        "attachment_id": made["id"],
        "page_id": page_id,
    }
    assert taken[str(rules["page.review_due"].id)] == {"page_id": page_id}


async def test_a_run_taken_up_again_is_told_the_same_event_kind(work: Work) -> None:
    """Decision 3 as changed in M7: a waiting or resumed run works with its term's
    assignment, whatever the owner edits meanwhile. The kind, the count and the ids
    are copied when the term fires; a take-up reads the copy, not the rule."""
    bench = work.bench
    rule = await ruled(bench, await _channel(work))
    await work.ticket("Neu")
    await take_in(bench, "ticket.created", T0)
    [run] = await runs_of(bench.session, rule.id)
    first = await automation_runs.assignment(bench.session, rule.org_id, run.id)
    assert first is not None and first.event is not None
    rule.event_type = "page.published"  # type: ignore[assignment]  # its owner edits the rule
    await bench.session.flush()
    again = await automation_runs.assignment(bench.session, rule.org_id, run.id)
    assert again is not None and again.event is not None
    assert (again.event.type, again.event.objects) == (first.event.type, first.event.objects)


async def test_what_a_run_is_told_outlasts_the_events_it_took(work: Work) -> None:
    """The cleanup may remove the events a term took; its run is still told the same
    kind, count and ids (the term's copy)."""
    bench = work.bench
    rule = await ruled(bench, await _channel(work))
    made = await work.ticket("Neu")
    await take_in(bench, "ticket.created", T0)
    [run] = await runs_of(bench.session, rule.id)
    await bench.session.execute(delete(AutomationEvent))
    told = await automation_runs.assignment(bench.session, rule.org_id, run.id)
    assert told is not None and told.event is not None
    assert (told.event.type, told.event.count) == ("ticket.created", 1)
    assert told.event.objects == [{"ticket_id": made["id"]}]

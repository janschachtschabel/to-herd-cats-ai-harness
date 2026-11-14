"""Whose rights an event rule's run has (plan M7 decision 8, review focus 2): its
owner's ∩ the agent's ∩ the audience of its place (a channel of the space: what a
viewer of the space sees), writing only into that space. Whoever caused the event
gains nothing and triggers nothing with their own rights. An event about an object
the run could not read (a draft, a page locked for AI) is not taken in at all; where
the place is closed to AI the term is logged `skipped_policy`."""

import uuid

from sqlalchemy import select

from app.core.permissions import SpaceRole
from app.modules.agents.models import StopReason
from app.modules.ai.models import AiPolicy
from app.modules.automations.event_models import AutomationEvent
from app.modules.automations.models import FiringOutcome
from app.modules.tickets.models import WorkItem
from app.modules.wiki.models import Page
from tests.factories_automations import T0, firings, ruled, runs_of
from tests.factories_tools import call
from tests.factories_wiki import new_page
from tests.factories_writing import Work, messages_in
from tests.test_automation_events import _channel, take_in
from tests.test_wiki_attachments import PNG, _uploaded

SECRET = "ENTWURF-GEHEIM-31"


async def test_the_run_is_its_owners_capped_at_the_place_whoever_caused_it(work: Work) -> None:
    """Alice owns the rule; the admin causes the event. Both see a draft and may
    write tickets in another space the agent belongs to: the run sees neither."""
    bench = work.bench
    bench.agent.level = 2
    await bench.join(work.private, SpaceRole.EDITOR)
    channel = await _channel(work)
    rule = await ruled(bench, channel)
    draft = await new_page(work.admin, work.space.id, "Entwurf", content_md=SECRET)
    await work.ticket("Neu")  # the admin causes the event
    await take_in(bench, "ticket.created", T0)
    [run] = await runs_of(bench.session, rule.id)
    assert run.user_id == bench.people.users["alice"].id  # never the admin's
    elsewhere = {"space_id": str(work.private.id), "title": "Woanders"}
    bench.stub.state.replies.extend(
        [
            call("read_page", page_id=draft["id"]),
            call("create_ticket", **elsewhere),
            {"content": "Fertig."},
        ]
    )
    assert await bench.run_next() == StopReason.COMPLETED
    assert SECRET not in bench.stub.state.texts()
    made = await bench.session.scalars(select(WorkItem).where(WorkItem.space_id == work.private.id))
    assert list(made) == []


async def _nothing_taken(work: Work, channel: uuid.UUID, rule_id: uuid.UUID) -> None:
    session = work.bench.session
    assert await runs_of(session, rule_id) == []
    assert await firings(session, rule_id) == []
    assert list(await session.scalars(select(AutomationEvent))) == []
    assert await messages_in(session, channel) == []


async def test_an_upload_to_a_draft_is_not_taken_in(work: Work) -> None:
    channel = await _channel(work)
    rule = await ruled(work.bench, channel, "attachment.uploaded")
    draft = await new_page(work.admin, work.space.id, "Entwurf", content_md=SECRET)
    await _uploaded(work.admin, draft, "plan.png", PNG)
    await take_in(work.bench, "attachment.uploaded", T0)
    await _nothing_taken(work, channel, rule.id)


async def test_a_page_locked_for_ai_is_not_taken_in(work: Work) -> None:
    channel = await _channel(work)
    rule = await ruled(work.bench, channel, "page.published")
    page = await work.bench.session.get(Page, uuid.UUID(await work.page()))
    assert page is not None
    page.no_ai = True
    await work.bench.session.flush()
    await take_in(work.bench, "page.published", T0)
    await _nothing_taken(work, channel, rule.id)


async def test_a_space_closed_to_ai_logs_skipped_policy(work: Work) -> None:
    channel = await _channel(work)
    rule = await ruled(work.bench, channel, "page.published")
    await work.page()
    work.space.ai_policy = AiPolicy.NONE
    await work.bench.session.flush()
    await take_in(work.bench, "page.published", T0)
    [logged] = await firings(work.bench.session, rule.id)
    assert (logged.outcome, logged.run_id) == (FiringOutcome.SKIPPED_POLICY, None)
    assert await runs_of(work.bench.session, rule.id) == []
    assert await messages_in(work.bench.session, channel) == []

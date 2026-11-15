"""Plan M6 task 6, rulings on proposals: the timeline and the activity name the agent
that proposed (a); a new page proposed at the top level, which has no thread, still
gives the space's moderators an activity entry, bound to the proposal (b), seen only
while they may edit the space's pages."""

import uuid
from typing import Any

from sqlalchemy import select

from app.core.outbox import Event, EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.toolbox import wiki_tools
from app.modules.proposals.handlers import notify_on_proposal, proposal_timeline
from app.modules.spaces.repository import SpaceRepository
from tests.factories_tools import tool_context
from tests.factories_writing import Work


async def _handle(work: Work) -> None:
    rows = await work.bench.session.scalars(
        select(EventOutbox).where(EventOutbox.type.like("proposal.%")).order_by(EventOutbox.id)
    )
    for row in rows.all():
        for handle in (proposal_timeline, notify_on_proposal):
            await handle(work.bench.session, Event.of(row))


async def _activity(work: Work, who: str = "admin") -> list[dict[str, Any]]:
    r = await getattr(work.bench.people, who).get("/api/activity")
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def _moderate(work: Work) -> None:
    admin = work.bench.people.users["admin"]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(admin.id), SpaceRole.MODERATOR
    )


async def test_a_top_level_proposal_reaches_the_moderators_activity(work: Work) -> None:
    await _moderate(work)
    ctx = await tool_context(work.bench)
    args = wiki_tools.ProposeNewPageArgs(
        space_id=work.space.id, title="Oben", content_md="x", reason="Fehlt noch"
    )
    result = await wiki_tools.propose_new_page(ctx, args)
    proposal_id = result.text.split("id=")[1].split(" ")[0].rstrip(";")
    await _handle(work)
    await _handle(work)  # delivered twice: still one entry
    (entry,) = await _activity(work)
    assert entry["reason"] == "proposal"
    assert entry["conversation"] is None and entry["message_id"] is None
    assert entry["proposal"] == {"id": proposal_id, "space_id": str(work.space.id)}
    assert entry["author"] == {"type": "agent", "id": str(work.bench.agent.id), "name": "Ava"}
    assert entry["snippet"] == ""
    count = (await work.bench.people.admin.get("/api/activity/count")).json()
    assert count["unread"] == 1
    done = await work.bench.people.admin.post(f"/api/activity/{entry['id']}/done")
    assert done.status_code in (200, 204), done.text
    # Seen only while the moderator may edit the space's pages.
    admin = work.bench.people.users["admin"]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(admin.id), SpaceRole.VIEWER
    )
    assert await _activity(work) == []


async def test_a_change_proposal_names_the_agent_in_timeline_and_activity(work: Work) -> None:
    await _moderate(work)
    page_id = await work.page()
    ctx = await tool_context(work.bench)
    args = wiki_tools.ProposePageChangeArgs(
        page_id=uuid.UUID(page_id), content_md="neu\n", reason="Besser"
    )
    assert (await wiki_tools.propose_page_change(ctx, args)).text.startswith("Proposal id=")
    await _handle(work)
    (entry,) = await _activity(work)
    assert entry["conversation"]["page_id"] == page_id and entry["proposal"] is None
    assert entry["author"] == {"type": "agent", "id": str(work.bench.agent.id), "name": "Ava"}
    thread = (await work.bench.people.admin.get(f"/api/pages/{page_id}/thread")).json()
    r = await work.bench.people.admin.get(f"/api/conversations/{thread['id']}/messages")
    (system,) = [m["system"] for m in r.json()["items"] if m["kind"] == "system"]
    assert system["key"] == "proposal.created"
    assert system["actor"] == {"id": str(work.bench.agent.id), "name": "Ava", "type": "agent"}

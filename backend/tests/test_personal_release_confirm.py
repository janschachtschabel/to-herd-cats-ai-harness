"""Module review M8 4, K5 and M8 5, L2: under the personal mark a tool on `confirm`
asks the usual release, and it is personal (the card says the content can be read by
others now or later, shows it in full and refuses what cannot be shown), whatever the
call would meet when it runs: a refusal now can be gone by the time she decides. The
one exception is a message into the run's own DM alone with her (it is marked)."""

import uuid
from typing import Any

import pytest
from sqlalchemy import select, update

from app.core.config import get_settings
from app.core.permissions import SpaceRole
from app.modules.agents.approvals.models import Approval
from app.modules.agents.approvals.shown import NOT_SHOWN
from app.modules.agents.run_models import StopReason
from app.modules.proposals.models import PageProposal
from app.modules.tickets.models import WorkItem
from tests.factories_external import Ext, call
from tests.factories_personal import decide, pending
from tests.factories_writing import Work
from tests.test_run_external_personal import SECRET, _personal


async def _confirm(ext: Ext, tool: str, name: str) -> None:
    """`tool` on `confirm`, her connector's search (`name`) still allowed."""
    version = (await ext.grants())["version"]
    tools = [{"tool": name, "policy": "allow"}, {"tool": tool, "policy": "confirm"}]
    put = {"tools": tools, "version": version}
    r = await ext.admin.put(f"{ext.agent_url}/tools", json=put)
    assert r.status_code == 200, r.text


async def _asked(ext: Ext, name: str, second: dict[str, Any]) -> dict[str, Any]:
    ext.bench.stub.state.replies.extend([call(name, q="meine"), second, {"content": "Ok."}])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() is None  # waits for a release
    (approval,) = await pending(ext.bench.people.alice)
    return approval


async def test_a_message_into_her_dm_alone_asks_no_personal_release(ext: Ext) -> None:
    name = await _personal(ext)  # level 3: post_message
    await _confirm(ext, "post_message", name)
    text = f"Gefunden: {SECRET}"
    post = call("post_message", conversation_id=ext.bench.dm_id, text=text)
    approval = await _asked(ext, name, post)
    assert approval["tool"] == "post_message" and approval["personal"] is False
    await decide(ext, approval, "approve")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    posted = [m for m in await ext.bench.messages() if m["body_md"] == text]
    assert [m["personal"] for m in posted] == [True]  # alone with her: marked


async def test_a_ticket_under_the_mark_asks_a_personal_release(ext: Ext, work: Work) -> None:
    name = await _personal(ext)
    await _confirm(ext, "create_ticket", name)
    ticket = call("create_ticket", space_id=str(work.space.id), title=f"Fund {SECRET}")
    approval = await _asked(ext, name, ticket)
    assert approval["tool"] == "create_ticket" and approval["personal"] is True
    assert approval["reads"] is False  # a write: its card says others can read it


async def test_a_read_tool_under_the_mark_asks_a_personal_release_that_reads(
    ext: Ext, work: Work
) -> None:
    """A read on `confirm` asks personally too, and says it reads (its card words it
    as a read, not as something others can read; fix wave 5 follow-up)."""
    ticket = await work.ticket()
    name = await _personal(ext)
    await _confirm(ext, "read_ticket", name)
    approval = await _asked(ext, name, call("read_ticket", key=ticket["key"]))
    assert approval["tool"] == "read_ticket" and approval["personal"] is True
    assert approval["reads"] is True


async def test_a_call_refused_when_asked_still_asks_a_personal_release(
    ext: Ext, work: Work
) -> None:
    """The parent ticket does not exist when the call is asked: the call would be
    refused then, yet the release is personal; she approves once it exists, and what
    is written is what she was shown."""
    name = await _personal(ext)
    await _confirm(ext, "create_ticket", name)
    second = call(
        "create_ticket", space_id=str(work.space.id), title=f"Fund {SECRET}", parent_key="HC-1"
    )
    approval = await _asked(ext, name, second)
    assert approval["personal"] is True
    await work.ticket("Eltern", kind="story")  # HC-1 exists now
    await decide(ext, approval, "approve")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    titles = list(await ext.bench.session.scalars(select(WorkItem.title)))
    assert f"Fund {SECRET}" in titles


async def test_a_page_change_too_large_to_show_is_refused_whatever_else_holds_it(
    ext: Ext, work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The agent may not edit the page's space yet (the call would be refused): the
    change is still one she must see in full to release, and it is too large."""
    name = await _personal(ext)
    await _confirm(ext, "propose_page_change", name)
    await work.bench.join(work.space, SpaceRole.VIEWER)  # no page.edit for the agent
    page_id = await work.page("Regeln", "1\n2\n3\n")
    monkeypatch.setattr(get_settings(), "diff_max_lines", 4)
    content = f"eins\n{SECRET}\ndrei\n"  # 4 + 4 lines: beyond
    change = call("propose_page_change", page_id=page_id, content_md=content, reason="neu")
    ext.bench.stub.state.replies.extend([call(name, q="meine"), change, {"content": "Ok."}])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert await pending(ext.bench.people.alice) == []
    asked = [e for e in await ext.tool_events() if e["name"] == "propose_page_change"]
    assert asked[-1]["text"] == NOT_SHOWN
    assert list(await ext.bench.session.scalars(select(PageProposal))) == []


async def test_a_release_not_asked_as_personal_under_the_mark_is_stale(
    ext: Ext, work: Work
) -> None:
    """A release the mark owes but that was not asked as personal (here: made so in
    the database) does not let the call write: it is stale, and the model may ask anew."""
    name = await _personal(ext)
    await _confirm(ext, "create_ticket", name)
    second = call("create_ticket", space_id=str(work.space.id), title=f"Fund {SECRET}")
    approval = await _asked(ext, name, second)
    await ext.bench.session.execute(
        update(Approval).where(Approval.id == uuid.UUID(approval["id"])).values(personal=False)
    )
    await decide(ext, approval, "approve")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    row = await ext.bench.session.get(Approval, uuid.UUID(approval["id"]))
    assert row is not None
    await ext.bench.session.refresh(row)
    assert row.outcome == "stale"
    titles = list(await ext.bench.session.scalars(select(WorkItem.title)))
    assert f"Fund {SECRET}" not in titles

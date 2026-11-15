"""Plan M6 task 6: every writing tool's effect is committed with its journal entry, so
a run whose worker died right after the tool (here: an exception nobody catches after
the call's transaction committed, as in `test_run_replay.py`) is taken up again,
replays the call from its journal and never writes twice. Also: which tools a run
offers at which level, and that their results reach the model framed."""

import uuid
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.run_models import StopReason
from app.modules.agents.toolbox import wiki_tools
from app.modules.agents.toolbox.catalog import CATALOG, offered
from app.modules.agents.toolbox.policy import Grant, allowed
from app.modules.messaging.models import Message, MessageKind
from app.modules.proposals.models import PageProposal
from app.modules.skills.proposal_models import SkillProposal
from app.modules.spaces.models import AgentWritePolicy
from app.modules.tickets.models import TicketPageLink, WorkItem
from app.modules.wiki.models import Page, PageVersion
from tests.factories_tickets import status_of
from tests.factories_tools import call
from tests.factories_writing import Work, alone_in, set_level
from tests.test_run_replay import Crash, die_after, take_up_again

WRITING = {
    "propose_page_change": 2,
    "propose_new_page": 2,
    "comment_ticket": 2,
    "set_ticket_status": 2,
    "create_ticket": 2,
    "link_ticket_page": 2,
    "propose_skill": 2,
    "update_memory": 2,
    "update_page": 3,
    "assign_ticket": 3,
    "post_message": 3,
}


def test_the_levels_offer_the_writing_tools() -> None:
    for name, level in WRITING.items():
        assert CATALOG[name].level == level
    names = {level: {s.name for s in allowed(level, offered(), {})} for level in (1, 2, 3)}
    assert not names[1] & set(WRITING)
    assert names[2] & set(WRITING) == {n for n, lv in WRITING.items() if lv == 2}
    assert names[3] >= set(WRITING)
    held = allowed(3, offered(), {"update_page": Grant.BLOCK})
    assert "update_page" not in {s.name for s in held}


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


Prepare = Callable[[Work], Awaitable[tuple[dict[str, Any], Callable[[], Awaitable[int]]]]]


async def _proposal(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    page = await work.page()
    args = {"page_id": page, "content_md": "neu\n", "reason": "r"}
    return args, lambda: _count(work.bench.session, PageProposal)


async def _new_page(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    args = {"space_id": str(work.space.id), "title": "N", "content_md": "x", "reason": "r"}
    return args, lambda: _count(work.bench.session, PageProposal)


def _agent_messages(work: Work) -> Callable[[], Awaitable[int]]:
    return lambda: _count(
        work.bench.session,
        Message,
        Message.kind == MessageKind.AGENT,
        Message.conversation_id != uuid.UUID(work.bench.dm_id),
    )


async def _comment(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    ticket = await work.ticket()
    return {"key": f"HC-{ticket['number']}", "text": "Erledige ich."}, _agent_messages(work)


async def _status(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    ticket = await work.ticket()
    review = await status_of(work.admin, work.space.id, "review")
    args = {"key": f"HC-{ticket['number']}", "status": review["name"]}
    return args, lambda: _count(work.bench.session, WorkItem, WorkItem.version > 1)


async def _create(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    args = {"space_id": str(work.space.id), "title": "Vom Agenten"}
    return args, lambda: _count(work.bench.session, WorkItem, WorkItem.reporter_type == "agent")


async def _link(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    ticket, page = await work.ticket(), await work.page()
    args = {"key": f"HC-{ticket['number']}", "page_id": page}
    return args, lambda: _count(work.bench.session, TicketPageLink)


async def _assign(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    ticket = await work.ticket()
    alice = work.bench.people.id("alice")
    args = {"key": f"HC-{ticket['number']}", "assignee_type": "user", "assignee_id": alice}
    return {**args, "reason": "Deins."}, _agent_messages(work)


async def _post(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    args = {"conversation_id": work.bench.dm_id, "text": "Zwischenstand"}
    return args, lambda: _count(
        work.bench.session,
        Message,
        Message.kind == MessageKind.AGENT,
        Message.body_md == "Zwischenstand",
    )


async def _skill(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    args = {
        "kind": "new",
        "name": "werkstatt-regeln",
        "space_id": str(work.space.id),
        "description": "d",
        "content": "c",
        "reason": "r",
    }
    return args, lambda: _count(work.bench.session, SkillProposal)


async def _memory(work: Work) -> tuple[dict[str, Any], Callable[[], Awaitable[int]]]:
    await alone_in(work)  # asked in Alice's DM alone with the agent
    args = {"space_id": str(work.space.id), "content": "Merke: Inventur."}
    return args, lambda: _count(
        work.bench.session, PageVersion, PageVersion.content_md == "Merke: Inventur."
    )


PREPARED: dict[str, Prepare] = {
    "propose_page_change": _proposal,
    "propose_new_page": _new_page,
    "comment_ticket": _comment,
    "set_ticket_status": _status,
    "create_ticket": _create,
    "link_ticket_page": _link,
    "assign_ticket": _assign,
    "post_message": _post,
    "propose_skill": _skill,
    "update_memory": _memory,
}


@pytest.mark.parametrize("name", sorted(PREPARED))
async def test_a_writing_tool_writes_once_when_its_run_is_taken_up_again(
    work: Work, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    await set_level(work.bench, 3)
    args, effects = await PREPARED[name](work)
    calling = {"tool_calls": [{"name": name, "arguments": args}]}  # args may hold `name`
    work.bench.stub.state.replies.extend([calling, {"content": "Done."}])
    await work.bench.say("Bitte erledigen")
    die_after(monkeypatch, "call_tool")
    with pytest.raises(Crash):
        await work.bench.run_next()
    monkeypatch.undo()
    assert await effects() == 1
    assert await take_up_again(work.bench) == StopReason.COMPLETED
    assert await effects() == 1  # replayed from the journal, not run again
    sent = work.bench.stub.state.texts()
    assert "<untrusted" in sent


async def test_update_page_writes_once_when_its_run_is_taken_up_again(
    work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    await set_level(work.bench, 3)
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    page_id = await work.page()
    posted = await work.bench.say("Bitte ändern")
    run_id = uuid.UUID(posted["agent_run"]["id"])
    writer = SimpleNamespace(binding=lambda: run_id)  # a run's preview is bound to the run
    page = await work.bench.session.get(Page, uuid.UUID(page_id))
    assert page is not None
    token = wiki_tools._token(writer, page, "neu\n")  # type: ignore[arg-type]
    args = {"page_id": page_id, "content_md": "neu\n", "reason": "r", "token": token}
    work.bench.stub.state.replies.extend([call("update_page", **args), {"content": "Done."}])
    die_after(monkeypatch, "call_tool")
    with pytest.raises(Crash):
        await work.bench.run_next()
    monkeypatch.undo()
    versions = lambda: _count(  # noqa: E731
        work.bench.session, PageVersion, PageVersion.page_id == uuid.UUID(page_id)
    )
    assert await versions() == 2
    assert await take_up_again(work.bench) == StopReason.COMPLETED
    assert await versions() == 2

"""Module review M8 4, K2: what a marked run writes carries no mark, so it may only be
what the asking person released. Memory is no exception (it reaches every later run
of the agent in its briefing, an automation's run and a run after "Neu beginnen"
included): under the mark `update_memory` waits for her release of exactly that
content like any write. Unreleased, nothing is written, and a later unmarked run can
send nothing of it to a server with a shared connector."""

from typing import Any

from app.modules.agents.memory_repository import MemoryRepository
from app.modules.agents.run_models import StopReason
from app.modules.wiki.models import Page
from tests.factories_automations import fire, placed
from tests.factories_external import Ext, call
from tests.factories_personal import asks_release, decide, pending
from tests.factories_writing import Work, alone_in, set_level
from tests.test_external_personal_mark_other_server import SECRET, _two_servers
from tests.test_personal_mark_fresh_start import _fresh_start


async def _remember(ext: Ext, work: Work, tracker: str, content: str) -> dict[str, Any]:
    """A run reads through her own connector, then wants to remember `content`."""
    ext.bench.stub.state.replies.extend(
        [
            call(tracker, q="meine"),  # her own connector: the run is marked
            call("update_memory", space_id=str(work.space.id), content=content),
            {"content": "Gemerkt."},
        ]
    )
    await ext.bench.say("Such meine Issues und merk dir das Ergebnis")
    return await asks_release(ext, await ext.bench.run_next())


async def _memory(ext: Ext, work: Work) -> str | None:
    bench = ext.bench
    found = await MemoryRepository(bench.session, bench.agent.org_id).get(
        bench.agent.id, work.space.id
    )
    if found is None:
        return None
    page = await bench.session.get(Page, found.page_id, populate_existing=True)
    assert page is not None
    return page.content_md


async def test_memory_written_under_the_mark_waits_for_her(ext: Ext, work: Work) -> None:
    """The review's case: unreleased, nothing is remembered; after "Neu beginnen" (which
    cancels the waiting run) the next run is unmarked, holds nothing of it, and sends
    nothing of it to the shared server."""
    names = await _two_servers(ext)
    await set_level(ext.bench, 3)  # update_memory
    await alone_in(work)  # nobody but Alice reads "Werkstatt" today
    approval = await _remember(ext, work, names["Tracker"], f"Merken: {SECRET}")
    assert SECRET in str(approval["args"])  # she sees exactly what would be written
    assert await _memory(ext, work) is None

    assert (await _fresh_start(ext)).status_code == 200  # her way out of the DM's mark
    assert await pending(ext.bench.people.alice) == []  # the waiting run is cancelled
    state = ext.bench.stub.state
    state.replies.extend(
        [
            call(names["Teamtracker"], q="weitergereicht"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Such im Team-Tracker nach dem, was du dir gemerkt hast")
    before = len(state.log)
    assert await ext.bench.run_next() == StopReason.COMPLETED
    first = str(state.log[before].body)  # the run's first model call, before any tool
    assert SECRET not in first and "Such meine Issues" not in first
    sent = [arguments for _, arguments in ext.stub.state.calls]
    assert not any(SECRET in str(arguments) for arguments in sent[1:]), sent
    assert await _memory(ext, work) is None


async def test_released_memory_is_written_and_unmarked(ext: Ext, work: Work) -> None:
    names = await _two_servers(ext)
    await set_level(ext.bench, 3)
    await alone_in(work)
    approval = await _remember(ext, work, names["Tracker"], "Merken: freigegeben")
    await decide(ext, approval, "approve")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert await _memory(ext, work) == "Merken: freigegeben"


async def test_an_automation_in_her_dm_reads_only_memory_she_released(ext: Ext, work: Work) -> None:
    """An automation's run in her DM gets no history, only its instruction and the
    agent's memory: that memory holds what she released and nothing she rejected."""
    names = await _two_servers(ext)
    await set_level(ext.bench, 3)
    await alone_in(work)
    rejected = await _remember(ext, work, names["Tracker"], f"Merken: {SECRET}")
    await decide(ext, rejected, "reject")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    released = await _remember(ext, work, names["Tracker"], "Merken: freigegeben")
    await decide(ext, released, "approve")
    assert await ext.bench.run_next() == StopReason.COMPLETED

    await placed(ext.bench, ext.bench.dm_id, instruction="Was hast du dir gemerkt?")
    await fire(ext.bench)
    state = ext.bench.stub.state
    state.replies.append({"content": "Bericht."})
    before = len(state.log)
    assert await ext.bench.run_next() == StopReason.COMPLETED
    first = str(state.log[before].body)
    assert "Merken: freigegeben" in first and SECRET not in first

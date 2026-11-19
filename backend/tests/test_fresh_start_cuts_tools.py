"""Module review M8 4, K3: "Neu beginnen" cuts everything the DM's runs could reach
of what came before: the history window, `read_conversation` (also the replies to a
message from before) and `search_past_runs` (nothing of a run from before the cut,
whatever its conversation). Memory she released stays (`test_personal_mark_memory
_released`)."""

import uuid
from typing import Any

from sqlalchemy import select

from app.modules.agents.run_models import EventKind, Run, RunEvent, StopReason
from app.modules.agents.toolbox.base import NOT_FOUND
from tests.factories_external import Ext, call
from tests.test_personal_mark_fresh_start import _fresh_start, _marked
from tests.test_run_external_personal import SECRET


async def _last(ext: Ext, name: str) -> dict[str, Any]:
    found = [e for e in await ext.tool_events() if e["name"] == name]
    return found[-1]


async def _unmarked_before(ext: Ext) -> None:
    ext.bench.stub.state.replies.append({"content": "Deine Lieblingsfarbe ist Blau."})
    await ext.bench.say("Merk dir: Lieblingsfarbe Blau")
    assert await ext.bench.run_next() == StopReason.COMPLETED


async def _search(ext: Ext, query: str) -> dict[str, Any]:
    ext.bench.stub.state.replies.extend(
        [call("search_past_runs", query=query), {"content": "Gesucht."}]
    )
    await ext.bench.say(f"Such nach {query}")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    return await _last(ext, "search_past_runs")


async def test_without_a_cut_past_runs_are_found(ext: Ext) -> None:
    await _marked(ext)
    await _unmarked_before(ext)
    assert "Blau" in (await _search(ext, "Blau"))["text"]


async def test_after_the_cut_search_past_runs_finds_nothing_from_before(ext: Ext) -> None:
    await _marked(ext)
    await _unmarked_before(ext)
    assert (await _fresh_start(ext)).status_code == 200
    for query in ("Blau", "Da:"):
        found = await _search(ext, query)
        assert "Blau" not in found["text"] and SECRET not in found["text"], found
        assert "personal" not in (found.get("read") or {})  # nothing marks the run
    run = await ext.bench.session.scalar(select(Run).order_by(Run.created_at.desc()))
    assert run is not None
    marks = await ext.bench.session.scalars(
        select(RunEvent).where(RunEvent.run_id == run.id, RunEvent.kind == EventKind.MARK)
    )
    assert list(marks) == []


async def test_after_the_cut_search_past_runs_finds_what_came_after(ext: Ext) -> None:
    await _marked(ext)
    assert (await _fresh_start(ext)).status_code == 200
    await _unmarked_before(ext)  # after the cut this time
    assert "Blau" in (await _search(ext, "Blau"))["text"]


async def test_after_the_cut_no_thread_of_a_message_from_before(ext: Ext) -> None:
    """A thread under a message from before the cut is from before, its later replies
    too: `read_conversation` does not find it."""
    await _marked(ext)
    old = next(m for m in await ext.bench.messages() if m["kind"] == "agent")
    dm = ext.bench.dm_id
    before = {"body_md": "Vorher im Thread", "parent_id": old["id"]}
    r = await ext.bench.people.alice.post(f"/api/conversations/{dm}/messages", json=before)
    assert r.status_code == 201, r.text
    assert (await _fresh_start(ext)).status_code == 200
    after = {"body_md": "Nachher im Thread", "parent_id": old["id"]}
    r = await ext.bench.people.alice.post(f"/api/conversations/{dm}/messages", json=after)
    assert r.status_code == 201, r.text
    ext.bench.stub.state.replies.extend(
        [call("read_conversation", replies_to=str(uuid.UUID(old["id"]))), {"content": "Ok."}]
    )
    await ext.bench.say("Lies den Thread von vorhin")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    read = await _last(ext, "read_conversation")
    assert "im Thread" not in read["text"] and read["text"] == NOT_FOUND, read
    assert "personal" not in (read.get("read") or {})

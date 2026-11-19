"""Module review M8 3, H1: every event of a run that carries the personal mark is the
asking person's alone. The run view (`/api/runs/{id}/events`) shows anyone else (the
agent's responsible person, `agent.manage`, an admin) each of its events redacted, the
whole run and not only what came after the mark, the way a result from a space they
cannot read comes redacted. Under the mark, `update_page`'s preview (the model's
content, with what she read) runs without a release, but never as a released call
and never visible to others; a `search_past_runs` hit from a marked run is the
asker's alone."""

from dataclasses import replace
from typing import Any

from sqlalchemy import select

from app.modules.agents.run_models import Run, StopReason
from app.modules.agents.toolbox.base import CallRef
from app.modules.agents.toolbox.writing import RELEASE_NEEDED, effect
from app.modules.spaces.models import AgentWritePolicy
from app.runtime.loop import ToolResult
from tests.factories_external import Ext, call
from tests.factories_tools import tool_context
from tests.factories_writing import Work
from tests.test_run_external_personal import SECRET, _personal

PAGE_WORDS = "Werkstattregel-77"


async def _events(client: Any, run_id: object) -> list[dict[str, Any]]:
    r = await client.get(f"/api/runs/{run_id}/events", params={"limit": 100})
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


async def _preview_under_the_mark(ext: Ext, work: Work) -> None:
    name = await _personal(ext)
    work.space.agent_write_policy = AgentWritePolicy.DIRECT
    await work.bench.session.flush()
    page = await work.page()
    state = ext.bench.stub.state
    state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    state.replies.extend(
        [
            call(
                "update_page", page_id=page, content_md=f"eins\n{SECRET} ist offen\n", reason="neu"
            ),
            {"content": "Ich habe dir die Vorschau gezeigt."},
        ]
    )
    await ext.bench.say("Schreib das in die Regeln")
    assert await ext.bench.run_next() == StopReason.COMPLETED  # the preview needs no release


async def _latest_run(ext: Ext) -> Run:
    run = (await ext.bench.session.scalars(select(Run).order_by(Run.created_at.desc()))).first()
    assert run is not None
    return run


async def _seen_by_admin(ext: Ext) -> list[str]:
    admin = ext.bench.people.admin  # the agent's responsible person, an editor of the space
    return [
        str(e["content"].get("text")) for e in await _events(admin, (await _latest_run(ext)).id)
    ]


async def test_a_preview_under_the_mark_is_not_shown_to_the_responsible_person(
    ext: Ext, work: Work
) -> None:
    await _preview_under_the_mark(ext, work)
    texts = await _seen_by_admin(ext)
    assert not any(SECRET in t for t in texts), texts
    mine = await _events(ext.bench.people.alice, (await _latest_run(ext)).id)
    assert any(SECRET in str(e["content"].get("text")) for e in mine)  # hers in full


async def test_a_personal_hit_of_search_past_runs_is_the_askers_alone(ext: Ext, work: Work) -> None:
    await _preview_under_the_mark(ext, work)
    ext.bench.stub.state.replies.extend(
        [call("search_past_runs", query="ist offen"), {"content": "Gefunden."}]
    )
    await ext.bench.say("Was wolltest du in die Regeln schreiben?")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    texts = await _seen_by_admin(ext)
    assert not any(SECRET in t for t in texts), texts
    (hit,) = [
        e
        for e in await _events(ext.bench.people.alice, (await _latest_run(ext)).id)
        if e["content"].get("name") == "search_past_runs"
    ]
    assert hit["content"]["attrs"].get("asker_only") == "true"


async def test_the_whole_marked_run_is_redacted_also_before_the_mark(ext: Ext, work: Work) -> None:
    """What the run read before her connector's result (a page the admin reads too)
    comes redacted as well: the model's words after it may repeat both."""
    name = await _personal(ext)
    page = await work.page(content_md=f"{PAGE_WORDS}\n")
    ext.bench.stub.state.replies.extend(
        [call("read_page", page_id=page), call(name, q="meine"), {"content": "Da."}]
    )
    await ext.bench.say("Lies die Regeln und such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    run = await _latest_run(ext)
    shown = await _events(ext.bench.people.admin, run.id)
    tools = [e for e in shown if e["kind"] == "tool_call"]
    assert {e["content"]["name"] for e in tools} == {"read_page", name}
    assert all(e["redacted"] and "text" not in e["content"] for e in tools)
    assert PAGE_WORDS not in str(shown)
    mine = await _events(ext.bench.people.alice, run.id)
    assert PAGE_WORDS in str(mine) and SECRET in str(mine)


async def test_an_unmarked_run_shows_the_responsible_person_what_she_may_read(
    ext: Ext, work: Work
) -> None:
    page = await work.page(content_md=f"{PAGE_WORDS}\n")
    ext.bench.stub.state.replies.extend([call("read_page", page_id=page), {"content": "Da."}])
    await ext.bench.say("Lies die Regeln")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    shown = await _events(ext.bench.people.admin, (await _latest_run(ext)).id)
    assert PAGE_WORDS in str(shown)  # the rule of readable spaces, unchanged


async def test_a_call_that_ran_without_her_release_never_writes(work: Work) -> None:
    """The host runs a call under the mark without a release only where the gate
    says it changes nothing (a preview); should such a call reach a write after
    all, `effect` refuses it instead of writing."""
    ctx = replace(await tool_context(work.bench), call=CallRef(1, "call-1"), previewing=True)
    ctx.reads.personal = True
    wrote: list[bool] = []

    async def write() -> ToolResult:
        wrote.append(True)
        return ToolResult("wiki", "saved", {})

    result = await effect(ctx, "wiki", {}, write)
    assert wrote == [] and result.failed and result.text == RELEASE_NEEDED

"""Module review M8 3, H4: a run that may read its conversation or search its earlier
runs is told in its instructions what a line starting with "(personal) " in their
results means: what the person read through her own connection, hers alone, and that
writes elsewhere then wait for her release. A run without those tools is not told."""

from app.modules.agents.personal_mark import PERSONAL_LINE, PERSONAL_LINES
from app.modules.agents.run_models import StopReason
from app.modules.agents.toolbox.catalog import CATALOG
from tests.factories_agents import Bench

TOLD_BY = ("read_conversation", "search_past_runs")


def test_the_note_names_the_line_and_the_release() -> None:
    assert PERSONAL_LINE.strip() in PERSONAL_LINES
    assert "release" in PERSONAL_LINES


async def test_a_run_with_those_tools_is_told(bench: Bench) -> None:
    bench.stub.state.replies.append({"content": "Hallo."})
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.COMPLETED
    body = str(bench.stub.state.log[-1].body)
    assert all(name in body for name in TOLD_BY)  # offered
    assert PERSONAL_LINES in body


async def test_a_run_without_them_is_not_told(bench: Bench) -> None:
    url = f"/api/agents/{bench.agent.id}/tools"
    version = (await bench.people.admin.get(url)).json()["version"]
    tools = [{"tool": name, "policy": "block"} for name in TOLD_BY]
    r = await bench.people.admin.put(url, json={"tools": tools, "version": version})
    assert r.status_code == 200, r.text
    bench.stub.state.replies.append({"content": "Hallo."})
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.COMPLETED
    assert PERSONAL_LINES not in str(bench.stub.state.log[-1].body)
    assert set(TOLD_BY) <= set(CATALOG)

"""What others read of a `search_past_runs` result in the run view (review M6 finding
10): the run view never shows anyone but the asker the model's own words (they are
the conversation's content), so a result that holds any hit of them, or any hit from
a run that read no space, comes redacted for everyone else, whatever spaces its other
hits came from. A result of tool results only keeps the usual rule."""

from typing import Any

from app.modules.agents.models import StopReason
from app.modules.spaces.models import Space
from tests.factories_agents import Bench
from tests.factories_tools import call
from tests.test_past_runs_tool import WORD, past_run, space

__all__ = ["space"]

SECRET = "Privatsache-31"


async def _tool_calls(bench: Bench, who: str, run_id: str) -> list[dict[str, Any]]:
    r = await getattr(bench.people, who).get(f"/api/runs/{run_id}/events?limit=100")
    assert r.status_code == 200, r.text
    return [e for e in r.json()["items"] if e["kind"] == "tool_call"]


async def _search_run(bench: Bench) -> str:
    bench.stub.state.replies.extend([call("search_past_runs", query=WORD), {"content": "Ok."}])
    posted = await bench.say("Was weißt du noch?")
    assert await bench.run_next() == StopReason.COMPLETED
    return str(posted["agent_run"]["id"])


async def test_dm_words_in_a_past_runs_result_stay_with_the_asker(
    bench: Bench, space: Space
) -> None:
    bench.stub.state.replies.append({"content": f"Unter uns: {SECRET} heißt {WORD}."})
    await bench.say("Merk dir das")
    assert await bench.run_next() == StopReason.COMPLETED  # read nothing
    await past_run(bench, space)  # read a page of the space
    run_id = await _search_run(bench)
    (mine,) = await _tool_calls(bench, "alice", run_id)
    assert SECRET in mine["content"]["text"] and not mine["redacted"]
    (theirs,) = await _tool_calls(bench, "admin", run_id)  # responsible, reads the space
    assert theirs["redacted"] and "text" not in theirs["content"]
    assert SECRET not in str(theirs)


async def test_the_agents_words_of_a_space_run_stay_with_the_asker(
    bench: Bench, space: Space
) -> None:
    await past_run(bench, space)  # its answer repeats the page: the model's words
    run_id = await _search_run(bench)
    (theirs,) = await _tool_calls(bench, "admin", run_id)
    assert theirs["redacted"] and "text" not in theirs["content"]

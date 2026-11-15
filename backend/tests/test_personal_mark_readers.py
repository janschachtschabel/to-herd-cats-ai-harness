"""Module review M8 2, finding G1: a message marked personal exists only where the
person is alone with the agent, and nobody else reads its body anywhere: not through
the search, the run view, the activity view, the `/mcp` tools, nor an admin's
inspection of the DM (it comes withheld there)."""

import json
from typing import Any

from app.modules.agents.run_models import StopReason
from tests.factories_external import Ext, call
from tests.factories_mcp_endpoint import Connect, text_of
from tests.factories_tokens import mcp_on, new_token
from tests.test_run_external_personal import SECRET, _personal

INSPECT = "/api/admin/dm-inspect"


async def _marked(ext: Ext) -> dict[str, Any]:
    """Alice reads through her own connector in her DM; the answer is marked."""
    name = await _personal(ext)
    ext.bench.stub.state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    posted = await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    (said,) = [m for m in await ext.bench.messages() if m["kind"] == "agent"]
    assert said["personal"] is True and SECRET in said["body_md"]
    return {"run_id": posted["agent_run"]["id"], "message": said}


async def test_the_search_finds_it_for_nobody(ext: Ext) -> None:
    """The message search finds people's messages only (`SEARCHABLE_SQL`), so an
    agent's marked answer is in nobody's results, hers included."""
    await _marked(ext)
    people = ext.bench.people
    query = {"q": "PRIVAT"}  # a word of the secret
    for who in ("alice", "bob", "carol", "admin"):
        found = (await getattr(people, who).get("/api/search", params=query)).json()
        assert SECRET not in json.dumps(found), who


async def test_the_run_view_shows_nobody_else_its_words(ext: Ext) -> None:
    marked = await _marked(ext)
    run = marked["run_id"]
    mine = (await ext.bench.people.alice.get(f"/api/runs/{run}/events?limit=100")).json()
    assert SECRET in json.dumps(mine)
    shown = await ext.bench.people.admin.get(f"/api/runs/{run}/events?limit=100")  # responsible
    assert shown.status_code == 200, shown.text
    assert SECRET not in shown.text


async def test_nobody_elses_activity_holds_it(ext: Ext) -> None:
    await _marked(ext)
    for who in ("bob", "carol", "admin"):
        r = await getattr(ext.bench.people, who).get("/api/activity?limit=100")
        assert r.status_code == 200 and SECRET not in r.text, who


async def test_the_mcp_tools_do_not_reach_it(ext: Ext, connect: Connect) -> None:
    await _marked(ext)
    await mcp_on(ext.admin)
    token = await new_token(ext.bench.people.alice, mode="write")
    async with connect(token["secret"]) as client:
        offered = {t.name for t in (await client.list_tools()).tools}
        assert not offered & {"read_conversation", "search_past_runs"}
        found = text_of(await client.call_tool("search", {"query": SECRET}))
    assert SECRET not in found


async def test_an_inspection_of_her_dm_shows_it_withheld(ext: Ext) -> None:
    marked = await _marked(ext)
    people = ext.bench.people
    body = {"conversation_id": ext.bench.dm_id, "reason": "Prüfung nach Hinweis, Fall 12"}
    granted = await people.admin.post(INSPECT, json=body)
    assert granted.status_code == 201, granted.text
    r = await people.admin.get(f"{INSPECT}/{granted.json()['id']}/messages?limit=100")
    assert r.status_code == 200, r.text
    assert SECRET not in r.text
    shown = {m["id"]: m for m in r.json()["items"]}
    withheld = shown[marked["message"]["id"]]
    assert withheld["personal"] is True and withheld["body_md"] == ""
    asked = [m for m in shown.values() if m["kind"] == "human"]
    assert [m["body_md"] for m in asked] == ["Such meine Issues"]  # the rest as before

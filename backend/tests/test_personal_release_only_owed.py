"""Module review M8 4, K5: under the personal mark a tool on `confirm` asks the usual
release; the card is personal (it says the content can be read by others now or
later, shows it in full and refuses what cannot be shown) only when the call owes
her release under the mark. A message into the DM alone with her owes none."""

from typing import Any

from app.modules.agents.run_models import StopReason
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

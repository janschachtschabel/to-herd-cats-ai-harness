"""Follow-up to plan M8 task 7: what a run read through the asking person's own
connector stays with that person. The result marks the run like a draft
(`Reads.personal`): nothing it writes afterwards may reach anyone else, neither a
tool's write into a shared channel nor its final answer in a channel; alone with the
person it goes on. A shared connector's result carries no mark. The mark is journaled
with the call, so a run taken up again keeps it."""

from typing import Any

import pytest
from sqlalchemy import select

from app.modules.agents.run_models import EventKind, RunEvent, StopReason
from app.modules.agents.toolbox.writing import PERSONAL
from app.modules.messaging.models import Message
from tests.factories_connectors import PERSONAL as MY_CONNECTORS
from tests.factories_connectors import make_connector
from tests.factories_external import Ext, call
from tests.factories_writing import Work, set_level
from tests.test_run_replay import Crash, die_after, take_up_again

SECRET = "PRIVAT-Gnu-4"


async def _channel(work: Work) -> str:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _personal(ext: Ext) -> str:
    """The server takes each person's own connector; Alice has hers."""
    await ext.patch_server(connector_scope="personal")
    await make_connector(ext.bench.people.alice, MY_CONNECTORS, mcp_server_id=ext.server["id"])
    return await _searching(ext)


async def _searching(ext: Ext) -> str:
    ext.stub.state.results["search_issues"] = {"text": SECRET}
    await ext.grant(search_issues="allow")
    await set_level(ext.bench, 3)  # `post_message`
    return await ext.name("search_issues")


async def _bodies(ext: Ext) -> list[str]:
    return list(await ext.bench.session.scalars(select(Message.body_md)))


async def _stop(ext: Ext) -> dict[str, Any]:
    content = await ext.bench.session.scalar(
        select(RunEvent.content).where(RunEvent.kind == EventKind.STOP)
    )
    assert content is not None
    return dict(content)


async def test_a_personal_result_is_not_posted_into_a_shared_channel(ext: Ext, work: Work) -> None:
    name, channel = await _personal(ext), await _channel(work)
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="meine"),
            call("post_message", conversation_id=channel, text=f"Gefunden: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Such meine Issues und sag es dem Team")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert ext.stub.state.calls == [("search_issues", {"q": "meine"})]
    assert PERSONAL in ext.bench.stub.state.texts()
    assert not any(SECRET in body for body in await _bodies(ext))
    *_, found, refused = await ext.tool_events()  # the call's result, the refused post
    assert found["read"]["personal"] is True and refused["text"] == PERSONAL


async def test_alone_with_the_person_the_run_goes_on(ext: Ext) -> None:
    name = await _personal(ext)
    dm = ext.bench.dm_id
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="meine"),
            call("post_message", conversation_id=dm, text=f"Zwischenstand: {SECRET}"),
            {"content": f"Gefunden: {SECRET}"},
        ]
    )
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    bodies = [m["body_md"] for m in await ext.bench.messages()]
    assert f"Zwischenstand: {SECRET}" in bodies and f"Gefunden: {SECRET}" in bodies


async def test_a_shared_connectors_result_carries_no_mark(ext: Ext, work: Work) -> None:
    connector = await make_connector(ext.admin, secret={"value": "tok-geteilt"})
    await ext.patch_server(connector_scope="shared", connector_id=connector["id"])
    name, channel = await _searching(ext), await _channel(work)
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="alle"),
            call("post_message", conversation_id=channel, text=f"Gefunden: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Such die Issues und sag es dem Team")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert f"Gefunden: {SECRET}" in await _bodies(ext)
    *_, found, posted = await ext.tool_events()
    assert "personal" not in found["read"] and posted["text"].startswith("Posted message")


async def test_the_final_answer_in_a_channel_is_refused(ext: Ext, work: Work) -> None:
    name, channel = await _personal(ext), await _channel(work)
    ext.bench.stub.state.replies.extend([call(name, q="meine"), {"content": f"Da: {SECRET}"}])
    r = await ext.bench.people.alice.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@Ava such meine Issues", "mentions": [str(ext.bench.agent.id)]},
    )
    assert r.status_code == 201, r.text
    assert await ext.bench.run_next() == StopReason.POLICY_BLOCKED
    assert not any(SECRET in body for body in await _bodies(ext))
    assert (await _stop(ext))["detail"] == "personal_connector"


async def test_a_run_taken_up_again_keeps_the_mark(
    ext: Ext, work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    name, channel = await _personal(ext), await _channel(work)
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="meine"),
            call("post_message", conversation_id=channel, text=f"Gefunden: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Such meine Issues und sag es dem Team")
    die_after(monkeypatch, "call_tool")  # the result is recorded, then the worker dies
    with pytest.raises(Crash):
        await ext.bench.run_next()
    monkeypatch.undo()
    assert await take_up_again(ext.bench) == StopReason.COMPLETED  # a new worker's memory
    assert ext.stub.state.calls == [("search_issues", {"q": "meine"})]
    assert PERSONAL in ext.bench.stub.state.texts()
    assert not any(SECRET in body for body in await _bodies(ext))

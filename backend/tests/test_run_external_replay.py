"""Plan M8 task 7, the journal rule for external calls: a committed step is never sent
again on replay, and a call whose outcome is unknown after a lost worker (it was sent,
its answer never recorded) is not sent again either, read or write: the model learns
that its outcome is unknown. Nothing secret reaches the journal, the logs or the
outbox: not the credential, and neither arguments nor results outside the journal."""

import json
import logging
from typing import Any

import pytest
from sqlalchemy import select

from app.core.outbox import EventOutbox
from app.modules.agents import external_step
from app.modules.agents.run_models import RunEvent, StopReason
from app.modules.agents.toolbox.external import OUTCOME_UNKNOWN
from tests.factories_connectors import make_connector
from tests.factories_external import Ext, call
from tests.test_run_external_writes import asked, decide
from tests.test_run_replay import Crash, die_after, take_up_again


def die_after_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    """The worker dies after the server answered, before the answer is recorded."""
    real = external_step.execute

    async def dying(*args: Any) -> Any:
        await real(*args)
        raise Crash

    monkeypatch.setattr(external_step, "execute", dying)


async def test_a_call_whose_answer_was_lost_is_not_sent_again(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    ext.bench.stub.state.replies.extend([call(name, q="x"), {"content": "Weiß nicht."}])
    await ext.bench.say("Bitte nachsehen")
    die_after_sending(monkeypatch)
    with pytest.raises(Crash):
        await ext.bench.run_next()
    monkeypatch.undo()
    assert ext.stub.state.calls == [("search_issues", {"q": "x"})]
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    assert ext.stub.state.calls == [("search_issues", {"q": "x"})]  # not sent again
    second = json.dumps(ext.bench.stub.state.log[-1].body["messages"])
    assert "external_outcome_unknown" in second
    assert [e["text"] for e in await ext.tool_events()] == [OUTCOME_UNKNOWN]


async def test_a_released_write_whose_answer_was_lost_is_not_sent_again(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    approval = await asked(ext, title="Einmal")
    assert (await decide(ext, approval, "approve")).status_code == 200
    die_after_sending(monkeypatch)
    with pytest.raises(Crash):
        await ext.bench.run_next()
    monkeypatch.undo()
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    assert ext.stub.state.calls == [("create_issue", {"title": "Einmal"})]
    shown = (await ext.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] == "ran"  # used up when it was sent


async def test_a_recorded_answer_is_replayed_without_a_second_call(
    ext: Ext, monkeypatch: pytest.MonkeyPatch
) -> None:
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    ext.stub.state.results["search_issues"] = {"text": "Issue 9"}
    ext.bench.stub.state.replies.extend([call(name, q="x"), {"content": "Issue 9."}])
    await ext.bench.say("Bitte nachsehen")
    die_after(monkeypatch, "call_tool")
    with pytest.raises(Crash):
        await ext.bench.run_next()
    monkeypatch.undo()
    assert await take_up_again(ext.bench) == StopReason.COMPLETED
    assert len(ext.stub.state.calls) == 1
    second = json.dumps(ext.bench.stub.state.log[-1].body["messages"])
    assert "Issue 9" in second and "external_outcome_unknown" not in second


async def test_nothing_secret_leaves_the_journal(
    ext: Ext, caplog: pytest.LogCaptureFixture
) -> None:
    """The shared connector's token goes on the wire to the server only; arguments
    and the result stay in the run's journal."""
    connector = await make_connector(ext.admin, secret={"value": "tok-Secret-77"})
    await ext.patch_server(connector_scope="shared", connector_id=connector["id"])
    ext.stub.state.require_header = ("authorization", "Bearer tok-Secret-77")
    ext.stub.state.results["search_issues"] = {"text": "RESULT-Zebra-5"}
    await ext.grant(search_issues="allow")
    name = await ext.name("search_issues")
    ext.bench.stub.state.replies.extend([call(name, q="ARG-Okapi-3"), {"content": "Gut."}])
    await ext.bench.say("Bitte nachsehen")
    with caplog.at_level(logging.DEBUG):
        assert await ext.bench.run_next() == StopReason.COMPLETED
    assert ext.stub.state.calls == [("search_issues", {"q": "ARG-Okapi-3"})]
    events = " ".join(
        json.dumps(e.content) for e in await ext.bench.session.scalars(select(RunEvent))
    )
    assert "RESULT-Zebra-5" in events and "tok-Secret-77" not in events
    logs = caplog.text + " ".join(str(r.__dict__) for r in caplog.records)
    for word in ("tok-Secret-77", "ARG-Okapi-3", "RESULT-Zebra-5"):
        assert word not in logs
    outbox = " ".join(str(e.payload) for e in await ext.bench.session.scalars(select(EventOutbox)))
    for word in ("tok-Secret-77", "ARG-Okapi-3", "RESULT-Zebra-5"):
        assert word not in outbox
    assert "tok-Secret-77" not in ext.bench.stub.state.texts()  # never to the model

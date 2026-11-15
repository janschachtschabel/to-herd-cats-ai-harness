"""Plan M6 task 7: a tool whose grant is `confirm` is offered; its call asks the person
who asked the run for a release (an approval bound to a fingerprint, a card in the
conversation, an activity entry) and the run waits. A release runs the call, unless
what it changes changed meanwhile (`approval_stale`) or the run lost its rights
(`rights_revoked`); a rejection gives the model `approval_rejected` with the reason;
nobody deciding in time ends the run `approval_expired`. Only the person asked
decides, and only while they could do it themselves."""

import uuid
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select, update

from app.core.config import Settings, get_settings
from app.core.models_base import utcnow
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents import control
from app.modules.agents.approvals.gate import fingerprint
from app.modules.agents.approvals.models import Approval
from app.modules.agents.run_models import Run, StopReason
from app.modules.messaging.live_events import of_event
from app.modules.proposals.models import PageProposal
from app.modules.spaces.repository import SpaceRepository
from app.modules.wiki.models import Page
from tests.factories_tools import call
from tests.factories_writing import Work, events

NEW = "eins\nZWEI\n"


async def confirm(work: Work, tool: str, policy: str = "confirm") -> None:
    bench = work.bench
    url = f"/api/agents/{bench.agent.id}/tools"
    put = {"tools": [{"tool": tool, "policy": policy}], "version": bench.agent.version}
    r = await bench.people.admin.put(url, json=put)
    assert r.status_code == 200, r.text


async def asked(work: Work, page_id: str) -> tuple[uuid.UUID, dict[str, Any]]:
    """A run that called `propose_page_change` (on `confirm`) and now waits."""
    await confirm(work, "propose_page_change")
    args = {"page_id": page_id, "content_md": NEW, "reason": "Klarer"}
    work.bench.stub.state.replies.extend(
        [call("propose_page_change", **args), {"content": "Erledigt."}]
    )
    posted = await work.bench.say("Bitte verbessern")
    assert await work.bench.run_next() is None  # waits
    r = await work.bench.people.alice.get("/api/approvals", params={"state": "pending"})
    assert r.status_code == 200, r.text
    (approval,) = r.json()["items"]
    return uuid.UUID(posted["agent_run"]["id"]), approval


async def decide(
    work: Work, approval: dict[str, Any], decision: str, who: str = "alice", **more: Any
) -> Any:
    body = {"decision": decision, "version": approval["version"], **more}
    client = getattr(work.bench.people, who)
    return await client.post(f"/api/approvals/{approval['id']}/decide", json=body)


async def proposals(work: Work) -> list[PageProposal]:
    return list((await work.bench.session.scalars(select(PageProposal))).all())


async def tool_texts(work: Work) -> str:
    return work.bench.stub.state.texts()


async def test_a_confirm_tool_is_offered_and_its_call_waits_for_a_release(work: Work) -> None:
    page_id = await work.page()
    run_id, approval = await asked(work, page_id)
    offered = [t["function"]["name"] for t in work.bench.stub.state.log[0].body["tools"]]
    assert "propose_page_change" in offered
    run = await work.bench.run_of(run_id)
    assert run.state == "waiting" and run.wait_until is not None
    assert run.wait_until - utcnow() > timedelta(hours=71)
    assert approval["tool"] == "propose_page_change" and approval["state"] == "pending"
    assert approval["outcome"] is None  # what became of the call: only once released
    assert approval["summary"] == f"propose_page_change: page_id={page_id}"
    assert approval["args"] == {"page_id": page_id, "content_md": NEW, "reason": "Klarer"}
    assert approval["diff_url"] == f"/api/approvals/{approval['id']}/diff"
    assert approval["conversation_id"] == work.bench.dm_id
    assert await proposals(work) == []  # nothing written yet
    # The card: the agent's message in the run's conversation, with the summary only.
    (card,) = [m for m in await work.bench.messages() if m["kind"] == "approval"]
    assert card["id"] == approval["message_id"]
    assert card["card"] == {"type": "approval", "id": approval["id"]}
    assert card["body_md"] == approval["summary"] and NEW not in card["body_md"]
    assert card["author"]["type"] == "agent" and card["run_id"] == str(run_id)
    # The activity entry of the person asked.
    activity = (await work.bench.people.alice.get("/api/activity")).json()["items"]
    assert [(a["reason"], a["message_id"]) for a in activity] == [("approval", card["id"])]
    # No content in the outbox.
    for event in await events(work.bench.session, "message.created"):
        assert NEW not in str(event.payload) and "Klarer" not in str(event.payload)
    # The fingerprint: tool, canonical arguments and the page's version.
    row = await work.bench.session.get(Approval, uuid.UUID(approval["id"]))
    assert row is not None and row.subjects[0]["kind"] == "page"
    # The call it waits for, as the run's journal names it (the client finds the call's
    # result there: run, rejected or stale).
    assert (approval["step"], approval["call_id"]) == (row.step, row.call_id)
    page = await work.bench.session.get(Page, uuid.UUID(page_id))
    assert page is not None and row.subjects[0]["version"] == page.version


async def test_a_release_runs_the_call_once(work: Work) -> None:
    page_id = await work.page()
    run_id, approval = await asked(work, page_id)
    r = await decide(work, approval, "approve")
    assert r.status_code == 200, r.text
    decided = r.json()
    assert decided["state"] == "approved" and decided["decided_by"] == work.bench.people.id("alice")
    assert decided["version"] == approval["version"] + 1
    assert (await work.bench.run_of(run_id)).state == "queued"
    (event,) = await events(work.bench.session, "approval.decided")
    assert set(event.payload) == {"approval_id", "run_id", "conversation_id", "message_id"}
    assert await work.bench.run_next() == StopReason.COMPLETED
    (proposal,) = await proposals(work)
    assert proposal.content_md == NEW and proposal.run_id == run_id
    # The API tells what became of the call (set where the call ran) and says so live.
    shown = (await work.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] == "ran" and shown["state"] == "approved"
    (settled,) = await events(work.bench.session, "approval.settled")
    assert settled.payload == {**event.payload}
    live = of_event(settled)
    assert live is not None and live.name == "card.changed"
    assert str(live.conversation_id) == settled.payload["conversation_id"]
    assert len(work.bench.stub.state.log) == 2  # the model was asked once before, once after
    again = await decide(work, decided, "reject")
    assert again.status_code == 409 and again.json()["error"]["code"] == "approval.decided"


async def test_a_rejection_tells_the_model_why_and_runs_nothing(work: Work) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    r = await decide(work, approval, "reject", reason="Bitte nicht jetzt")
    assert r.status_code == 200 and r.json()["reason"] == "Bitte nicht jetzt"
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert await proposals(work) == []
    sent = await tool_texts(work)
    assert "approval_rejected" in sent and "Bitte nicht jetzt" in sent and "<untrusted" in sent
    shown = (await work.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] is None


async def test_a_changed_page_makes_the_release_stale(work: Work) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    assert (await decide(work, approval, "approve")).status_code == 200
    page = await work.bench.session.get(Page, uuid.UUID(page_id))
    assert page is not None
    page.content_md, page.version = "eins\nzwei\nvon Hand\n", page.version + 1
    await work.bench.session.flush()
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert await proposals(work) == []
    assert "approval_stale" in await tool_texts(work)
    # The API reports the release as stale (set in the transaction that found it so),
    # for the person asked and for anyone else who sees the card.
    url = f"/api/approvals/{approval['id']}"
    for who in ("alice", "admin"):
        shown = (await getattr(work.bench.people, who).get(url)).json()
        assert shown["outcome"] == "stale" and shown["state"] == "approved", who
    (settled,) = await events(work.bench.session, "approval.settled")
    assert settled.payload["approval_id"] == approval["id"]


async def test_rights_lost_while_waiting_end_the_run(work: Work) -> None:
    page_id = await work.page()
    run_id, approval = await asked(work, page_id)
    assert (await decide(work, approval, "approve")).status_code == 200
    # The agent only views the space now: the run may not propose there any more.
    await work.bench.join(work.space, SpaceRole.VIEWER)
    assert await work.bench.run_next() == StopReason.RIGHTS_REVOKED
    assert await proposals(work) == []
    shown = (await work.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] is None  # the call neither ran nor was found stale


async def test_a_grant_blocked_while_waiting_runs_nothing(work: Work) -> None:
    """A tool blocked meanwhile is no longer offered: the call it waited on does not
    run, and the model is told the tool is unknown (as for any tool taken away)."""
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    assert (await decide(work, approval, "approve")).status_code == 200
    await confirm(work, "propose_page_change", "block")
    assert await work.bench.run_next() == StopReason.COMPLETED
    assert await proposals(work) == []
    assert "unknown tool 'propose_page_change'" in await tool_texts(work)


async def test_only_the_person_asked_decides(work: Work) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    url = f"/api/approvals/{approval['id']}"
    # The responsible person (also agent.manage) sees it without the arguments.
    shown = await work.bench.people.admin.get(url)
    assert shown.status_code == 200 and shown.json()["args"] is None
    assert shown.json()["diff_url"] is None
    r = await decide(work, approval, "approve", who="admin")
    assert r.status_code == 403 and r.json()["error"]["code"] == "approval.not_addressed"
    # Anyone else: as if there were none.
    hidden = await work.bench.people.bob.get(url)
    unknown = await work.bench.people.bob.get(f"/api/approvals/{uuid.uuid4()}")
    assert hidden.status_code == unknown.status_code == 404
    assert hidden.json()["error"]["code"] == unknown.json()["error"]["code"]
    r = await decide(work, approval, "approve", who="bob")
    assert r.status_code == 404
    for path in ("/diff",):
        assert (await work.bench.people.admin.get(url + path)).status_code == 404
    # The person asked must be able to do it now: Alice only views the space.
    alice = work.bench.people.users["alice"]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(alice.id), SpaceRole.VIEWER
    )
    r = await decide(work, approval, "approve")
    assert r.status_code == 403 and r.json()["error"]["code"] == "approval.not_permitted"
    stale = await decide(work, {**approval, "version": 99}, "approve")
    assert stale.status_code == 403  # still not permitted: rights before the version


async def test_the_version_is_checked(work: Work) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    r = await decide(work, {**approval, "version": approval["version"] + 1}, "approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "approval.version_conflict"


async def test_the_diff_shows_the_page_now_against_the_call(work: Work) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    r = await work.bench.people.alice.get(approval["diff_url"])
    assert r.status_code == 200, r.text
    hunks = r.json()
    assert {"kind": "insert", "lines": ["ZWEI"]} in hunks
    assert {"kind": "delete", "lines": ["zwei"]} in hunks


async def test_nobody_deciding_in_time_ends_the_run(work: Work) -> None:
    page_id = await work.page()
    run_id, approval = await asked(work, page_id)
    past = utcnow() - timedelta(seconds=1)
    await work.bench.session.execute(update(Run).where(Run.id == run_id).values(wait_until=past))
    await work.bench.session.execute(
        update(Approval).where(Approval.id == uuid.UUID(approval["id"])).values(expires_at=past)
    )
    r = await decide(work, approval, "approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "approval.expired"
    async with work.bench.unit()() as session:
        assert await control.sweep_waiting(session) == 1
    run = await work.bench.run_of(run_id)
    assert run.stop_reason == StopReason.APPROVAL_EXPIRED
    shown = (await work.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["state"] == "expired"
    notices = [m["system"]["new"]["value"] for m in await work.bench.messages() if m["system"]]
    assert notices == ["approval_expired"]


async def test_a_cancelled_run_takes_no_decision(work: Work) -> None:
    page_id = await work.page()
    run_id, approval = await asked(work, page_id)
    async with work.bench.unit()() as session:
        alice = work.bench.people.users["alice"]
        assert await control.request_cancel(session, work.bench.agent.org_id, run_id, alice.id)
    r = await decide(work, approval, "approve")
    assert r.status_code == 409 and r.json()["error"]["code"] == "approval.run_ended"
    async with work.bench.unit()() as session:
        assert await control.sweep_waiting(session) == 1
    assert (await work.bench.run_of(run_id)).stop_reason == StopReason.CANCELLED
    shown = (await work.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["state"] == "expired"


async def test_the_wait_is_configurable(work: Work, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_AI_APPROVAL_HOURS", "2")
    assert Settings().ai_approval_hours == 2
    monkeypatch.setattr(get_settings(), "ai_approval_hours", 2.0)
    page_id = await work.page()
    run_id, approval = await asked(work, page_id)
    run = await work.bench.run_of(run_id)
    assert run.wait_until is not None
    assert timedelta(hours=1) < run.wait_until - utcnow() <= timedelta(hours=2)


async def test_my_pending_approvals_page_and_refuse_a_bad_cursor(work: Work) -> None:
    page_id = await work.page()
    _, approval = await asked(work, page_id)
    mine = await work.bench.people.alice.get("/api/approvals", params={"limit": 1})
    assert [a["id"] for a in mine.json()["items"]] == [approval["id"]]
    assert mine.json()["next_cursor"] is None
    assert (await work.bench.people.bob.get("/api/approvals")).json()["items"] == []
    done = await work.bench.people.alice.get("/api/approvals", params={"state": "approved"})
    assert done.json()["items"] == []
    bad = await work.bench.people.alice.get("/api/approvals", params={"cursor": "%%%"})
    assert bad.status_code == 422


def test_the_fingerprint_binds_tool_arguments_and_versions() -> None:
    from app.modules.agents.toolbox.base import Subject

    page = uuid.uuid4()
    one = fingerprint("t", {"a": 1, "b": 2}, [Subject("page", page, 3, None)])
    assert one == fingerprint("t", {"b": 2, "a": 1}, [Subject("page", page, 3, None)])
    assert one != fingerprint("t", {"a": 1, "b": 2}, [Subject("page", page, 4, None)])
    assert one != fingerprint("u", {"a": 1, "b": 2}, [Subject("page", page, 3, None)])
    assert one != fingerprint("t", {"a": 1, "b": 3}, [Subject("page", page, 3, None)])

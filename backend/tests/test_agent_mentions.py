"""Plan M6 task 8: a person's mention of an agent in a channel or a thread starts the
agent's run, which answers in the mentioning message's thread; without `ai.use`, or
for an agent that is no member of the space, nothing starts and nothing tells; one run
per conversation; agents mentioning agents start nothing."""

import uuid
from typing import Any

from sqlalchemy import func, select

from app.core.authorship import Authorship
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.agents.models import AgentStatus, Run, StopReason
from app.modules.ai.models import AiPolicy
from app.modules.messaging.service import MessageService
from app.modules.spaces.repository import SpaceRepository
from tests.factories_agents import assign_default, make_agent
from tests.factories_messaging import post
from tests.factories_spaces import personal_space_of
from tests.factories_wiki import new_page, publish
from tests.factories_writing import Work
from tests.test_access import actor_of


async def _channel(work: Work) -> str:
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "werkbank"})
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


async def _replies(work: Work, message_id: object) -> list[dict[str, Any]]:
    r = await work.bench.people.alice.get(f"/api/messages/{message_id}/replies?limit=100")
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def _runs(work: Work) -> int:
    return int(await work.bench.session.scalar(select(func.count()).select_from(Run)) or 0)


async def test_a_mention_in_a_channel_is_answered_in_its_thread(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    agent = str(bench.agent.id)
    asked = await post(bench.people.alice, channel, "@Ava wie spät?")
    assert asked["agent_run"] is None  # no mentions sent: an @ in the text asks nobody
    r = await bench.people.alice.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@Ava was steht an?", "mentions": [agent]},
    )
    assert r.status_code == 201, r.text
    written = r.json()
    assert written["agent_run"]["reason"] is None and written["agent_run"]["agent_id"] == agent
    assert written["not_notified"] == []  # the agent it asked is not "not notified"
    run = await bench.run_of(written["agent_run"]["id"])
    assert (run.trigger_message_id, run.work_item_id, run.chain_depth) == (
        uuid.UUID(written["id"]),
        None,
        0,
    )
    bench.stub.state.replies.append({"content": "Die Inventur."})
    assert await bench.run_next() == StopReason.COMPLETED
    assert "was steht an?" in bench.stub.state.texts()
    (answer,) = await _replies(work, written["id"])
    assert (answer["kind"], answer["body_md"], answer["author"]["type"]) == (
        "agent",
        "Die Inventur.",
        "agent",
    )
    root = (await bench.people.alice.get(f"/api/messages/{written['id']}")).json()
    assert root["reply_count"] == 1
    shown = (await bench.people.alice.get(f"/api/runs/{run.id}")).json()
    assert shown["trigger_message_id"] == written["id"] and shown["chain_depth"] == 0
    assert shown["place"]["kind"] == "channel"


async def test_a_mention_in_a_reply_reads_and_answers_that_thread(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    root = await post(bench.people.admin, channel, "Wer macht die Inventur?")
    asked = await post(
        bench.people.alice,
        channel,
        "Frag doch Ava",
        parent_id=root["id"],
    )
    assert asked["agent_run"] is None
    r = await bench.people.alice.post(
        f"/api/conversations/{channel}/messages",
        json={
            "body_md": "@Ava weißt du es?",
            "parent_id": root["id"],
            "mentions": [str(bench.agent.id)],
        },
    )
    assert r.status_code == 201 and r.json()["agent_run"]["id"] is not None
    bench.stub.state.replies.append({"content": "Bob."})
    assert await bench.run_next() == StopReason.COMPLETED
    sent = bench.stub.state.texts()
    assert "Wer macht die Inventur?" in sent and "weißt du es?" in sent
    replies = await _replies(work, root["id"])
    assert [m["body_md"] for m in replies][-1] == "Bob."


async def test_a_stopped_mention_run_notes_it_in_the_thread(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    r = await bench.people.alice.post(
        f"/api/conversations/{channel}/messages",
        json={"body_md": "@Ava bitte", "mentions": [str(bench.agent.id)]},
    )
    written = r.json()
    cancel = await bench.people.alice.post(f"/api/runs/{written['agent_run']['id']}/cancel")
    assert cancel.status_code == 200, cancel.text
    (notice,) = await _replies(work, written["id"])
    assert notice["kind"] == "system"
    assert (
        notice["system"]["key"] == "run.stopped" and notice["system"]["new"]["value"] == "cancelled"
    )
    top = (await bench.people.alice.get(f"/api/conversations/{channel}/messages")).json()
    assert [m["id"] for m in top["items"]] == [written["id"]]


async def test_without_ai_use_a_mention_starts_nothing_and_tells_nothing(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    await assign_default(bench.people.admin, None)  # nobody has `ai.use` now
    unknown = str(uuid.uuid4())
    for mentioned in (str(bench.agent.id), unknown):
        r = await bench.people.alice.post(
            f"/api/conversations/{channel}/messages",
            json={"body_md": "@Ava?", "mentions": [mentioned]},
        )
        assert r.status_code == 201, r.text
        assert r.json()["agent_run"] is None and r.json()["not_notified"] == [mentioned]
    assert await _runs(work) == 0
    directory = await bench.people.alice.get("/api/directory?type=agent")
    assert directory.status_code == 200 and directory.json()["items"] == []


async def test_an_agent_outside_the_space_or_a_draft_is_not_asked(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    outside = await make_agent(bench.session, bench.people, bench.connection.id, name="Olaf")
    draft = await make_agent(
        bench.session, bench.people, bench.connection.id, name="Dora", status="draft"
    )
    await SpaceRepository(bench.session).set_member(
        work.space.id, Principal.agent(draft.id), SpaceRole.EDITOR
    )
    for agent in (outside, draft):
        r = await bench.people.alice.post(
            f"/api/conversations/{channel}/messages",
            json={"body_md": "@?", "mentions": [str(agent.id)]},
        )
        assert r.json()["agent_run"] is None and r.json()["not_notified"] == [str(agent.id)]
    assert await _runs(work) == 0


async def test_one_run_per_conversation_and_refusals_name_their_code(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    body = {"body_md": "@Ava eins", "mentions": [str(bench.agent.id)]}
    first = await bench.people.alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert first.json()["agent_run"]["id"] is not None
    again = await bench.people.admin.post(f"/api/conversations/{channel}/messages", json=body)
    assert again.json()["agent_run"] == {
        "id": None,
        "reason": "run.waiting",
        "agent_id": str(bench.agent.id),
    }
    assert await _runs(work) == 1
    bench.agent.status = AgentStatus.PAUSED
    await bench.session.flush()
    paused = await bench.people.alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert paused.json()["agent_run"]["reason"] == "agent.paused"


async def test_agents_mentioning_agents_start_nothing(work: Work) -> None:
    bench, channel = work.bench, await _channel(work)
    body = {"body_md": "@Ava los", "mentions": [str(bench.agent.id)]}
    first = await bench.people.alice.post(f"/api/conversations/{channel}/messages", json=body)
    run_id = uuid.UUID(first.json()["agent_run"]["id"])
    bench.stub.state.replies.append({"content": "Fertig."})
    assert await bench.run_next() == StopReason.COMPLETED
    other = await make_agent(bench.session, bench.people, bench.connection.id, name="Bert")
    await SpaceRepository(bench.session).set_member(
        work.space.id, Principal.agent(other.id), SpaceRole.EDITOR
    )
    alice = await actor_of(bench.session, bench.people.users["alice"])
    by = Authorship(Principal.agent(bench.agent.id), run_id)
    posted = await MessageService(bench.session).post(
        alice,
        uuid.UUID(channel),
        "@Bert du bist dran",
        client_id=uuid.uuid4(),
        mentions=[other.id],
        by=by,
    )
    assert posted.agent_run is None and await _runs(work) == 1


async def test_someone_elses_personal_agent_is_not_asked(work: Work) -> None:
    """Even a personal agent made a member of the space (it never is through the API)
    answers its owner only: a mention by anyone else tells nothing."""
    bench, channel = work.bench, await _channel(work)
    r = await bench.people.admin.post(
        "/api/agents", json={"name": "Pia", "personal": True, "status": "active"}
    )
    assert r.status_code == 201, r.text
    pia = uuid.UUID(r.json()["id"])
    await SpaceRepository(bench.session).set_member(
        work.space.id, Principal.agent(pia), SpaceRole.EDITOR
    )
    body = {"body_md": "@Pia?", "mentions": [str(pia)]}
    asked = await bench.people.alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert asked.json()["agent_run"] is None and asked.json()["not_notified"] == [str(pia)]
    assert await _runs(work) == 0


async def test_a_thread_in_a_space_closed_to_ai_never_reaches_the_model(work: Work) -> None:
    """What a run is asked in a channel is that space's content: its policy counts."""
    bench, channel = work.bench, await _channel(work)
    body = {"body_md": "@Ava Kennwort ZEBRA-4711", "mentions": [str(bench.agent.id)]}
    r = await bench.people.alice.post(f"/api/conversations/{channel}/messages", json=body)
    assert r.json()["agent_run"]["id"] is not None
    work.space.ai_policy = AiPolicy.NONE
    await bench.session.flush()
    assert await bench.run_next() == StopReason.POLICY_BLOCKED
    assert "ZEBRA-4711" not in bench.stub.state.texts()
    (notice,) = await _replies(work, r.json()["id"])
    assert notice["system"]["new"]["value"] == "policy_blocked"


async def test_its_owner_asks_a_personal_agent_in_a_page_thread_of_their_space(work: Work) -> None:
    bench = work.bench
    r = await bench.people.alice.post(
        "/api/agents", json={"name": "Pia", "personal": True, "status": "active"}
    )
    pia = r.json()["id"]
    personal = await personal_space_of(bench.session, bench.people.users["alice"])
    page = await publish(
        bench.people.alice, await new_page(bench.people.alice, personal.id, "Notiz")
    )
    made = await bench.people.alice.get(f"/api/pages/{page['id']}/thread")
    assert made.status_code == 200, made.text
    body = {"body_md": "@Pia merk dir das", "mentions": [pia]}
    asked = await bench.people.alice.post(
        f"/api/conversations/{made.json()['id']}/messages", json=body
    )
    assert asked.json()["agent_run"]["id"] is not None
    assert asked.json()["agent_run"]["agent_id"] == pia

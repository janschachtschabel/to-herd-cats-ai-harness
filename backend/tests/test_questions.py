"""Plan M6 task 7: `ask_user` posts the agent's question as a card in the run's
conversation (with an activity entry) and the run waits; only the person asked
answers (bounded text), once; the answer comes back to the model as an untrusted
tool result; nobody answering in time ends the run `waiting_timeout`."""

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import update

from app.core.models_base import utcnow
from app.modules.agents import control
from app.modules.agents.approvals.models import MAX_ANSWER_CHARS
from app.modules.agents.models import Run, StopReason
from tests.factories_agents import Bench
from tests.factories_tools import call


async def asking(bench: Bench) -> tuple[uuid.UUID, dict[str, Any]]:
    bench.stub.state.replies.extend(
        [call("ask_user", question="Welcher Bereich?"), {"content": "Danke."}]
    )
    posted = await bench.say("Leg los")
    assert await bench.run_next() is None
    (card,) = [m for m in await bench.messages() if m["kind"] == "question"]
    r = await bench.people.alice.get(f"/api/questions/{card['card']['id']}")
    assert r.status_code == 200, r.text
    return uuid.UUID(posted["agent_run"]["id"]), r.json()


async def answer(bench: Bench, question: dict[str, Any], text: str, who: str = "alice") -> Any:
    client = getattr(bench.people, who)
    body = {"text": text, "version": question["version"]}
    return await client.post(f"/api/questions/{question['id']}/answer", json=body)


async def test_the_answer_goes_back_to_the_model(bench: Bench) -> None:
    run_id, question = await asking(bench)
    assert question["question"] == "Welcher Bereich?" and question["state"] == "pending"
    assert question["conversation_id"] == bench.dm_id
    (card,) = [m for m in await bench.messages() if m["kind"] == "question"]
    assert card["body_md"] == "Welcher Bereich?" and card["card"]["type"] == "question"
    activity = (await bench.people.alice.get("/api/activity")).json()["items"]
    assert [(a["reason"], a["message_id"]) for a in activity] == [("question", card["id"])]
    r = await answer(bench, question, "Der Werkstatt-Bereich")
    assert r.status_code == 200 and r.json()["state"] == "answered"
    assert r.json()["answer"] == "Der Werkstatt-Bereich"
    assert (await bench.run_of(run_id)).state == "queued"
    assert await bench.run_next() == StopReason.COMPLETED
    sent = bench.stub.state.texts()
    assert "Der Werkstatt-Bereich" in sent and "<untrusted" in sent
    again = await answer(bench, r.json(), "Noch was")
    assert again.status_code == 409 and again.json()["error"]["code"] == "question.answered"


async def test_only_the_person_asked_answers(bench: Bench) -> None:
    _, question = await asking(bench)
    shown = await bench.people.admin.get(f"/api/questions/{question['id']}")  # responsible
    assert shown.status_code == 200 and shown.json()["answer"] is None
    r = await answer(bench, question, "x", who="admin")
    assert r.status_code == 403 and r.json()["error"]["code"] == "question.not_addressed"
    hidden = await bench.people.bob.get(f"/api/questions/{question['id']}")
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "question.not_found"
    assert (await answer(bench, question, "x", who="bob")).status_code == 404
    too_long = await answer(bench, question, "x" * (MAX_ANSWER_CHARS + 1))
    assert too_long.status_code == 422
    stale = await answer(bench, {**question, "version": 5}, "x")
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "question.version_conflict"


async def test_nobody_answering_ends_the_run(bench: Bench) -> None:
    run_id, question = await asking(bench)
    past = utcnow() - timedelta(seconds=1)
    await bench.session.execute(update(Run).where(Run.id == run_id).values(wait_until=past))
    async with bench.unit()() as session:
        assert await control.sweep_waiting(session) == 1
    assert (await bench.run_of(run_id)).stop_reason == StopReason.WAITING_TIMEOUT
    shown = (await bench.people.alice.get(f"/api/questions/{question['id']}")).json()
    assert shown["state"] == "expired"
    r = await answer(bench, shown, "spät")
    assert r.status_code == 409 and r.json()["error"]["code"] == "question.expired"

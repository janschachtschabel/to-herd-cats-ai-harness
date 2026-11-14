"""Only the person a run asks reads its words on an approval or a question (review M6
finding 6), as in the run view: for everyone else who may see the card (the agent's
responsible person, `agent.manage`), `question` and the approval's `reason` are null
and `redacted` is true. The card in the conversation is the place's own."""

import uuid

from sqlalchemy import select

from app.modules.agents.approvals.models import RunQuestion
from app.modules.messaging.models import Conversation, ConversationKind
from tests.factories_tools import call
from tests.factories_writing import Work
from tests.test_approvals import asked, decide


async def test_only_the_person_asked_reads_the_question(work: Work) -> None:
    bench = work.bench
    await bench.say("Frag mich was")
    bench.stub.state.replies.append(call("ask_user", question="Wie lautet dein Geheimnis-4711?"))
    assert await bench.run_next() is None  # waits
    question = await bench.session.scalar(select(RunQuestion))
    assert question is not None
    mine = await bench.people.alice.get(f"/api/questions/{question.id}")
    assert mine.status_code == 200, mine.text
    assert mine.json()["question"] == "Wie lautet dein Geheimnis-4711?"
    assert mine.json()["redacted"] is False
    theirs = await bench.people.admin.get(f"/api/questions/{question.id}")
    assert theirs.status_code == 200, theirs.text
    assert "Geheimnis-4711" not in theirs.text
    assert (theirs.json()["question"], theirs.json()["redacted"]) == (None, True)
    dm = await bench.session.scalar(
        select(Conversation.kind).where(Conversation.id == uuid.UUID(bench.dm_id))
    )
    assert dm == ConversationKind.DM


async def test_only_the_person_asked_reads_the_reason_of_a_rejection(work: Work) -> None:
    _, approval = await asked(work, await work.page())
    assert approval["redacted"] is False
    r = await decide(work, approval, "reject", reason="Wegen Geheimnis-4711")
    assert r.status_code == 200 and r.json()["reason"] == "Wegen Geheimnis-4711"
    theirs = await work.bench.people.admin.get(f"/api/approvals/{approval['id']}")
    assert theirs.status_code == 200, theirs.text
    assert "Geheimnis-4711" not in theirs.text
    assert (theirs.json()["reason"], theirs.json()["redacted"]) == (None, True)
    assert theirs.json()["summary"] == approval["summary"]  # tool and ids stay

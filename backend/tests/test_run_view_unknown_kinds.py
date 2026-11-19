"""Module review M8 3, H6: the run view passes over an event kind it does not know (a
newer release's, written while pods of this one still serve during a rolling
upgrade) instead of answering 500. The asker and everyone else get the events it
knows, in order."""

from sqlalchemy import text

from app.core.models_base import utcnow
from app.modules.agents.run_models import Run, RunEvent, StopReason
from tests.factories_agents import Bench


async def test_an_unknown_event_kind_is_passed_over(bench: Bench) -> None:
    bench.stub.state.replies.append({"content": "Hallo."})
    await bench.say("Hallo")
    assert await bench.run_next() == StopReason.COMPLETED
    run = await bench.session.scalar(Run.__table__.select().with_only_columns(Run.id))
    # A newer release's kind: its check is not this release's (rolled back with the test).
    await bench.session.execute(text("ALTER TABLE run_event DROP CONSTRAINT ck_run_event_kind"))
    bench.session.add(
        RunEvent(
            org_id=bench.agent.org_id,
            run_id=run,
            attempt=1,
            seq=50,
            kind="from_the_future",
            content={"step": 9},
            created_at=utcnow(),
        )
    )
    await bench.session.flush()
    for who in ("alice", "admin"):
        r = await getattr(bench.people, who).get(f"/api/runs/{run}/events", params={"limit": 100})
        assert r.status_code == 200, (who, r.text)
        kinds = [e["kind"] for e in r.json()["items"]]
        assert "from_the_future" not in kinds and kinds[0] == "model_call" and "stop" in kinds

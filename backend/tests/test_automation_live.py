"""`automation.changed` live (plan M7 task 7): every change of an automation (through
the API, a pause by the system, a take-over) writes one outbox event with ids only;
the worker turns it into one `automation.changed` per person who may see the
automation (its owner, its agent's responsible person, the managers of its place's
space, `agent.manage`), with the automation's and the space's id and nothing else."""

import json
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select

from app.core.outbox import Event, EventOutbox
from app.core.principal import Principal
from app.modules.automations.firing import fire_next
from app.modules.automations.live import CHANGED, LIVE, automation_live
from app.modules.messaging.live_decode import decode
from app.modules.messaging.live_publish import of_event
from app.modules.spaces.repository import SpaceRepository
from tests.factories_writing import Work
from tests.live_helpers import LiveServer, drain
from tests.live_people import Person, stranger
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_automation_api import BASE, DAILY, NOW, SECRET, clock
from tests.test_automation_changes import in_channel, post
from tests.test_automation_due_loop import _place

__all__ = ["clock"]


async def _sources(work: Work, automation_id: str) -> list[EventOutbox]:
    stmt = (
        select(EventOutbox)
        .where(EventOutbox.type == CHANGED, EventOutbox.subject_id == uuid.UUID(automation_id))
        .order_by(EventOutbox.id)
    )
    return list((await work.bench.session.scalars(stmt)).all())


async def test_every_change_writes_one_event_with_ids_only(work: Work) -> None:
    made = await in_channel(work)  # Bob manages the space
    alice, bob = work.bench.people.alice, work.bench.people.bob
    path = f"{BASE}/{made['id']}"
    steps = [
        alice.patch(path, json={"version": 1, "instruction": "Neu"}),
        post(bob, made, "pause", 2),
        post(bob, made, "resume", 3),
        alice.post(f"{path}/run"),
        post(bob, made, "take-over", 4),
    ]
    for step in steps:
        r = await step
        assert r.status_code == 200, r.text
    rows = await _sources(work, made["id"])
    assert len(rows) == 6  # made, changed, paused, resumed, run now, taken over
    for row in rows:
        assert row.payload == {"automation_id": made["id"]}
        assert row.space_id == work.space.id
    assert (await bob.delete(f"{path}?version=5")).status_code == 204
    assert len(await _sources(work, made["id"])) == 7


async def test_a_pause_by_the_system_writes_one_too(work: Work) -> None:
    made = await in_channel(work)
    alice = work.bench.people.users["alice"]
    await SpaceRepository(work.bench.session).remove_member(work.space.id, Principal.user(alice.id))
    before = len(await _sources(work, made["id"]))
    fired = await fire_next(work.bench.session, NOW + timedelta(days=1))
    assert fired is not None and fired.paused == "owner"
    assert len(await _sources(work, made["id"])) == before + 1


async def test_the_worker_tells_each_person_who_may_see_it(work: Work) -> None:
    """Alice owns it, the admin is the agent's responsible person (and `agent.manage`),
    Bob manages the space; Carol and the guest see nothing of it."""
    made = await in_channel(work)
    (source,) = await _sources(work, made["id"])
    await automation_live(work.bench.session, Event.of(source))
    stmt = select(EventOutbox).where(EventOutbox.type == LIVE).order_by(EventOutbox.id)
    rows = (await work.bench.session.scalars(stmt)).all()
    people = work.bench.people
    assert {r.payload["user_id"] for r in rows} == {
        people.id("alice"),
        people.id("admin"),
        people.id("bob"),
    }
    for row in rows:
        assert set(row.payload) == {"user_id", "automation_id"}
        assert SECRET not in json.dumps(row.payload)
    live = of_event(Event.of(rows[0]))
    assert live is not None and live.automation_id == uuid.UUID(made["id"])
    assert decode(live.payload()) == live
    frame = live.frame().decode()
    assert frame.startswith(f"event: {LIVE}\n")
    data = json.loads(frame.split("data: ", 1)[1])
    assert data == {"automation_id": made["id"], "space_id": str(work.space.id)}


async def _automation(owner: Person, place: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "agent_id": str(place["agent"]),
        "place": {"type": "dm"},
        "instruction": SECRET,
        "schedule": DAILY,
    }
    r = await owner.client.post("/api/automations", json=payload)
    assert r.status_code == 201, r.text
    made: dict[str, Any] = r.json()
    return made


async def test_the_stream_of_its_owner_hears_of_it_and_no_other(
    real_db: RealDb,
    live: LiveServer,
    pair: tuple[Person, Person],
    make_real_client: MakeRealClient,
    openai_stub: OpenAIStub,
) -> None:
    owner, member = pair
    outsider = await stranger(real_db, live)
    place = await _place(real_db, make_real_client, openai_stub)
    await drain(real_db.database)
    mine, theirs, other = (
        await owner.stream(real_db),
        await member.stream(real_db),
        await outsider.stream(real_db),
    )
    made = await _automation(owner, place)
    await drain(real_db.database)
    event = await mine.until_event(LIVE)
    assert event.data == {"automation_id": made["id"], "space_id": None}
    await theirs.expect_nothing()
    await other.expect_nothing()
    for stream in (mine, theirs, other):
        await stream.close()

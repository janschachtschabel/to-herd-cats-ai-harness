"""Making an automation through the API (plan M7 decisions 4, 5, 12, 14): each kind
with its next terms, the places (DM, channel, a ticket's thread opened when saving),
the rules (an agent that is no member of the space, event rules for managers only,
personal agents), the cap, the preview and its refusals, and 404 for the invisible."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.outbox import EventOutbox
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.audit.models import AuditLog
from app.modules.automations import service
from app.modules.automations.models import Automation
from app.modules.messaging.models import Conversation
from app.modules.spaces.repository import SpaceRepository
from tests.factories_writing import Work
from tests.support.clock import SettableClock
from tests.test_personal_agents import created as personal_agent
from tests.test_personal_agents import switch

NOW = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)  # a Monday, 09:00 in Berlin
BASE = "/api/automations"
SECRET = "GEHEIMER-AUFTRAG-31"
DAILY = {"kind": "recurring", "cron": "0 9 * * *", "time_zone": "Europe/Berlin"}


@pytest.fixture(autouse=True)
def clock(monkeypatch: pytest.MonkeyPatch) -> SettableClock:
    at = SettableClock(NOW)
    monkeypatch.setattr(service, "CLOCK", at)
    return at


def body(
    work: Work, place: dict[str, Any], schedule: dict[str, Any], **more: Any
) -> dict[str, Any]:
    return {
        "agent_id": str(work.bench.agent.id),
        "place": place,
        "instruction": SECRET,
        "schedule": schedule,
        **more,
    }


async def make(client: AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
    r = await client.post(BASE, json=payload)
    assert r.status_code == 201, r.text
    made: dict[str, Any] = r.json()
    return made


async def channel(work: Work, space_id: object | None = None) -> str:
    r = await work.admin.post(
        f"/api/spaces/{space_id or work.space.id}/channels",
        json={"name": f"c{uuid.uuid4().hex[:6]}"},
    )
    assert r.status_code == 201, r.text
    return str(r.json()["id"])


def refused(r: Response, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code


async def manage(work: Work, who: str = "alice") -> None:
    user = work.bench.people.users[who]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(user.id), SpaceRole.ADMIN
    )


async def test_a_recurring_automation_in_the_dm_comes_with_its_next_terms(work: Work) -> None:
    alice = work.bench.people.alice
    made = await make(alice, body(work, {"type": "dm"}, DAILY))
    first = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)  # 09:00 in Berlin tomorrow
    assert made["kind"] == "recurring" and made["state"] == "active"
    assert (made["paused_reason"], made["version"], made["last_run"]) == (None, 1, None)
    assert datetime.fromisoformat(made["next_due_at"]) == first
    upcoming = [datetime.fromisoformat(t) for t in made["upcoming"]]
    assert upcoming == [first + timedelta(days=d) for d in range(5)]
    assert made["place"] == {
        "type": "dm",
        "conversation_id": work.bench.dm_id,
        "space_id": None,
        "name": None,
        "ticket_number": None,
    }
    assert made["owner"] == {"id": work.bench.people.id("alice"), "name": "Alice"}
    assert made["agent"] == {"id": str(work.bench.agent.id), "name": "Ava"}
    assert made["instruction"] == SECRET
    assert made["abilities"] == {
        "edit": True,
        "pause": True,
        "resume": False,
        "delete": True,
        "run": True,
        "take_over": False,
    }
    got = await alice.get(f"{BASE}/{made['id']}")
    assert got.status_code == 200 and got.json() == made


async def test_a_once_is_due_at_its_instant_and_never_in_the_past(work: Work) -> None:
    alice = work.bench.people.alice
    at = NOW + timedelta(hours=3)
    made = await make(alice, body(work, {"type": "dm"}, {"kind": "once", "at": at.isoformat()}))
    assert datetime.fromisoformat(made["next_due_at"]) == at
    assert [datetime.fromisoformat(t) for t in made["upcoming"]] == [at]
    past = {"kind": "once", "at": (NOW - timedelta(minutes=1)).isoformat()}
    refused(
        await alice.post(BASE, json=body(work, {"type": "dm"}, past)), 422, "automation.in_the_past"
    )


async def test_a_heartbeat_in_a_channel_beats_inside_its_hours(work: Work) -> None:
    beat = {
        "kind": "heartbeat",
        "interval_minutes": 60,
        "active_days": [1, 2, 3, 4, 5],
        "active_from": "10:00",
        "active_until": "12:00",
        "time_zone": "Europe/Berlin",
    }
    place = {"type": "channel", "conversation_id": await channel(work)}
    made = await make(work.bench.people.alice, body(work, place, beat))
    terms = [datetime.fromisoformat(t) for t in made["upcoming"]]
    monday, hour = datetime(2026, 11, 16, 9, tzinfo=UTC), timedelta(hours=1)  # 10:00 Berlin
    day = timedelta(days=1)
    assert terms == [monday, monday + hour, monday + day, monday + day + hour, monday + 2 * day]
    assert datetime.fromisoformat(made["next_due_at"]) == monday
    assert made["place"]["type"] == "channel" and made["place"]["space_id"] == str(work.space.id)
    assert (made["interval_minutes"], made["active_days"]) == (60, [1, 2, 3, 4, 5])


async def test_an_event_rule_is_for_who_manages_the_space(work: Work) -> None:
    alice = work.bench.people.alice
    rule = {"kind": "event", "event_type": "page.published"}
    place = {"type": "channel", "conversation_id": await channel(work)}
    refused(await alice.post(BASE, json=body(work, place, rule)), 403, "automation.not_allowed")
    await manage(work)
    made = await make(alice, body(work, place, rule))
    assert (made["kind"], made["next_due_at"], made["upcoming"]) == ("event", None, [])
    assert (made["event_type"], made["quiet_seconds"]) == ("page.published", 300)
    assert (made["abilities"]["edit"], made["abilities"]["run"]) == (True, False)  # no event
    dm = await alice.post(BASE, json=body(work, {"type": "dm"}, rule))
    refused(dm, 422, "automation.invalid_place")
    filtered = {**rule, "filter_ticket_kind": "bug"}
    refused(
        await alice.post(BASE, json=body(work, place, filtered)), 422, "automation.invalid_filter"
    )


async def test_a_tag_filter_names_a_tag_of_the_space_or_a_system_tag(work: Work) -> None:
    await manage(work)
    alice, admin = work.bench.people.alice, work.admin
    other = await admin.post("/api/tags", json={"name": "fremd", "space_id": str(work.private.id)})
    assert other.status_code == 201, other.text
    own = await admin.post("/api/tags", json={"name": "eigen", "space_id": str(work.space.id)})
    rule = {"kind": "event", "event_type": "ticket.created", "filter_tag_id": other.json()["id"]}
    place = {"type": "channel", "conversation_id": await channel(work)}
    refused(await alice.post(BASE, json=body(work, place, rule)), 422, "automation.invalid_filter")
    made = await make(alice, body(work, place, {**rule, "filter_tag_id": own.json()["id"]}))
    assert made["filter_tag_id"] == own.json()["id"]


async def test_a_ticket_place_opens_the_tickets_thread_when_saved(work: Work) -> None:
    ticket = await work.ticket()
    session = work.bench.session
    threads = select(Conversation).where(Conversation.work_item_id == uuid.UUID(ticket["id"]))
    await session.execute(
        delete(Conversation).where(Conversation.work_item_id == uuid.UUID(ticket["id"]))
    )
    assert (await session.scalars(threads)).all() == []  # a ticket from before its thread
    place = {"type": "ticket", "ticket_number": ticket["number"]}
    made = await make(work.bench.people.alice, body(work, place, DAILY))
    (thread,) = (await session.scalars(threads)).all()
    assert made["place"] == {
        "type": "ticket",
        "conversation_id": str(thread.id),
        "space_id": str(work.space.id),
        "name": None,
        "ticket_number": ticket["number"],
    }
    unknown = await work.bench.people.alice.post(
        BASE, json=body(work, {"type": "ticket", "ticket_number": 99999}, DAILY)
    )
    refused(unknown, 404, "ticket.not_found")


async def test_a_channel_needs_an_agent_that_is_a_member_of_its_space(work: Work) -> None:
    alice = work.bench.people.alice
    place = {"type": "channel", "conversation_id": await channel(work, work.private.id)}
    r = await alice.post(BASE, json=body(work, place, DAILY))
    refused(r, 422, "automation.agent_not_member")


async def test_who_may_not_post_in_the_channel_makes_none_there(work: Work) -> None:
    """Bob sees nothing of the team space: its channel does not exist for him."""
    place = {"type": "channel", "conversation_id": await channel(work)}
    r = await work.bench.people.bob.post(BASE, json=body(work, place, DAILY))
    refused(r, 404, "conversation.not_found")


async def test_a_personal_agent_works_only_for_its_owner_and_in_her_dm(work: Work) -> None:
    bench = work.bench
    assert (await switch(bench, True)).status_code == 200
    pia = await personal_agent(bench.people.alice, status="active")
    mine = {**body(work, {"type": "dm"}, DAILY), "agent_id": pia["id"]}
    made = await make(bench.people.alice, mine)
    assert made["agent"]["name"] == "Pia"
    refused(await bench.people.bob.post(BASE, json=mine), 404, "agent.not_found")
    place = {"type": "channel", "conversation_id": await channel(work)}
    elsewhere = {**body(work, place, DAILY), "agent_id": pia["id"]}
    refused(await bench.people.alice.post(BASE, json=elsewhere), 422, "automation.agent_not_member")


async def test_a_person_owns_at_most_the_cap(work: Work, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "ai_automations_max", 2)
    alice = work.bench.people.alice
    once = {"kind": "once", "at": (NOW + timedelta(hours=1)).isoformat()}
    first = await make(alice, body(work, {"type": "dm"}, once))
    await make(alice, body(work, {"type": "dm"}, DAILY))
    refused(await alice.post(BASE, json=body(work, {"type": "dm"}, DAILY)), 409, "automation.limit")
    row = await work.bench.session.get(Automation, uuid.UUID(first["id"]))
    assert row is not None
    row.state, row.next_due_at = "done", None  # type: ignore[assignment]
    await work.bench.session.flush()
    await make(alice, body(work, {"type": "dm"}, DAILY))  # a done one does not count


@pytest.mark.parametrize(
    ("schedule", "code"),
    [
        (
            {"kind": "recurring", "cron": "*/5 * * * *", "time_zone": "UTC"},
            "automation.too_frequent",
        ),
        ({"kind": "recurring", "cron": "0 9 * *", "time_zone": "UTC"}, "automation.invalid_cron"),
        (
            {"kind": "recurring", "cron": "0 9 31 2 *", "time_zone": "UTC"},
            "automation.invalid_cron",
        ),
        (
            {"kind": "recurring", "cron": "0 9 * * *", "time_zone": "Mars/Base"},
            "automation.invalid_time_zone",
        ),
        (
            {
                "kind": "heartbeat",
                "interval_minutes": 10,
                "active_days": [1],
                "active_from": "09:00",
                "active_until": "17:00",
                "time_zone": "UTC",
            },
            "automation.too_frequent",
        ),
        (
            {
                "kind": "heartbeat",
                "interval_minutes": 2000,
                "active_days": [1],
                "active_from": "09:00",
                "active_until": "17:00",
                "time_zone": "UTC",
            },
            "automation.invalid_interval",
        ),
        (
            {
                "kind": "heartbeat",
                "interval_minutes": 30,
                "active_days": [8],
                "active_from": "09:00",
                "active_until": "17:00",
                "time_zone": "UTC",
            },
            "automation.invalid_hours",
        ),
    ],
)
async def test_the_preview_refuses_what_cannot_be_scheduled(
    work: Work, schedule: dict[str, Any], code: str
) -> None:
    r = await work.bench.people.alice.post(f"{BASE}/preview", json={"schedule": schedule})
    refused(r, 422, code)
    made = await work.bench.people.alice.post(BASE, json=body(work, {"type": "dm"}, schedule))
    refused(made, 422, code)


async def test_the_preview_names_the_next_five_terms(work: Work) -> None:
    r = await work.bench.people.alice.post(f"{BASE}/preview", json={"schedule": DAILY})
    assert r.status_code == 200, r.text
    first = datetime(2026, 11, 17, 8, 0, tzinfo=UTC)
    assert [datetime.fromisoformat(t) for t in r.json()["terms"]] == [
        first + timedelta(days=d) for d in range(5)
    ]


async def test_who_may_not_see_it_finds_no_automation(work: Work) -> None:
    made = await make(work.bench.people.alice, body(work, {"type": "dm"}, DAILY))
    for client in (work.bench.people.bob, work.bench.people.alice):
        target = made["id"] if client is work.bench.people.bob else str(uuid.uuid4())
        refused(await client.get(f"{BASE}/{target}"), 404, "automation.not_found")


async def test_its_instruction_goes_into_no_audit_entry_outbox_event_or_log(
    work: Work, caplog: pytest.LogCaptureFixture
) -> None:
    made = await make(work.bench.people.alice, body(work, {"type": "dm"}, DAILY))
    session = work.bench.session
    audit = (
        await session.scalars(select(AuditLog).where(AuditLog.target_id == uuid.UUID(made["id"])))
    ).all()
    assert [a.action for a in audit] == ["automation.created"]
    assert set(audit[0].details) == {"agent_id", "conversation_id", "kind"}
    events = (await session.scalars(select(EventOutbox))).all()
    assert all(SECRET not in str(e.payload) for e in events)
    assert SECRET not in caplog.text

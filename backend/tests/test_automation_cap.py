"""The cap per person (plan M7 decision 12): at most `HERD_AI_AUTOMATIONS_MAX` open
automations (active or paused) per owner, wherever a row becomes open for a person:
making one, giving a done `once` a new instant (it is active again) and taking one
over (review M7, finding 4)."""

import uuid
from datetime import timedelta

import pytest

from app.core.config import get_settings
from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.automations.models import Automation
from app.modules.spaces.repository import SpaceRepository
from tests.factories_writing import Work
from tests.test_automation_api import BASE, DAILY, NOW, body, channel, clock, make

__all__ = ["clock"]


async def test_a_once_brought_back_counts_toward_the_cap(
    work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A done `once` does not count; given a new instant it is active again and must
    count (else N done ones give N automations beyond the cap)."""
    monkeypatch.setattr(get_settings(), "ai_automations_max", 1)
    alice = work.bench.people.alice
    once = {"kind": "once", "at": (NOW + timedelta(hours=1)).isoformat()}
    first = await make(alice, body(work, {"type": "dm"}, once))
    row = await work.bench.session.get(Automation, uuid.UUID(first["id"]))
    assert row is not None
    row.state, row.next_due_at = "done", None  # type: ignore[assignment]
    await work.bench.session.flush()
    await make(alice, body(work, {"type": "dm"}, DAILY))  # the cap of 1 is taken
    again = await alice.patch(
        f"{BASE}/{first['id']}", json={"version": first["version"], "schedule": once}
    )
    assert again.status_code == 409 and again.json()["error"]["code"] == "automation.limit", (
        again.status_code,
        again.text[:200],
    )


async def test_a_once_brought_back_within_the_cap_is_active_again(
    work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "ai_automations_max", 1)
    alice = work.bench.people.alice
    once = {"kind": "once", "at": (NOW + timedelta(hours=1)).isoformat()}
    first = await make(alice, body(work, {"type": "dm"}, once))
    row = await work.bench.session.get(Automation, uuid.UUID(first["id"]))
    assert row is not None
    row.state, row.next_due_at = "done", None  # type: ignore[assignment]
    await work.bench.session.flush()
    again = await alice.patch(
        f"{BASE}/{first['id']}", json={"version": first["version"], "schedule": once}
    )
    assert again.status_code == 200 and again.json()["state"] == "active", again.text


async def test_a_take_over_counts_toward_the_takers_cap(
    work: Work, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bob (a manager of the space, at his cap) takes Alice's automation over: he
    would then own more than `HERD_AI_AUTOMATIONS_MAX` (decision 12)."""
    monkeypatch.setattr(get_settings(), "ai_automations_max", 1)
    bob_user = work.bench.people.users["bob"]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(bob_user.id), SpaceRole.ADMIN
    )
    place = {"type": "channel", "conversation_id": await channel(work)}
    made = await make(work.bench.people.alice, body(work, place, DAILY))
    bob = work.bench.people.bob
    mine = await make(bob, body(work, place, DAILY))  # Bob's one
    taken = await bob.post(f"{BASE}/{made['id']}/take-over", json={"version": made["version"]})
    assert taken.status_code == 409 and taken.json()["error"]["code"] == "automation.limit", (
        taken.status_code,
        taken.text[:120],
    )
    r = await bob.delete(f"{BASE}/{mine['id']}?version={mine['version']}")
    assert r.status_code == 204, r.text
    taken = await bob.post(f"{BASE}/{made['id']}/take-over", json={"version": made["version"]})
    assert taken.status_code == 200, taken.text

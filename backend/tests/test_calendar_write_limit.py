"""Calendar writes count towards the person's write limit (plan M9 task 18, J10;
`auth/write_limits.COUNTED`): making, renaming and archiving a calendar are content
writes like pages and messages, and so is making an event; reading calendars and
events never counts."""

from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.core.metrics import REGISTRY
from tests.factories import MakeUser, login
from tests.factories_calendar import new_calendar, new_event
from tests.factories_spaces import MakeSpace


def _limited() -> float:
    return REGISTRY.get_sample_value("herd_rate_limited_total", {"area": "write"}) or 0.0


def _refused(answer: Any) -> None:
    assert answer.status_code == 429, answer.text
    assert answer.json()["error"]["code"] == "rate.limited"
    assert 1 <= int(answer.headers["retry-after"]) <= 60


async def test_calendar_writes_beyond_the_limit_answer_429(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    moderator, other = await make_user(), await make_user()
    team = await make_space("team", members=[(moderator, "moderator"), (other, "moderator")])
    mod: AsyncClient = await make_client(csrf=True)
    await login(mod, moderator.email)
    monkeypatch.setattr(get_settings(), "write_rate_per_minute", 3)
    before = _limited()
    made = await new_calendar(mod, team.id, "Urlaub")  # 1
    renamed = await mod.patch(
        f"/api/calendars/{made['id']}", json={"name": "Ferien", "version": made["version"]}
    )
    assert renamed.status_code == 200, renamed.text  # 2
    archived = await mod.delete(
        f"/api/calendars/{made['id']}", params={"version": renamed.json()["version"]}
    )
    assert archived.status_code == 204, archived.text  # 3
    _refused(await mod.post(f"/api/spaces/{team.id}/calendars", json={"name": "Zu viel"}))
    kept = await new_calendar(await _other(make_client, other.email), team.id, "Andere")
    _refused(await mod.patch(f"/api/calendars/{kept['id']}", json={"name": "X", "version": 1}))
    _refused(await mod.delete(f"/api/calendars/{kept['id']}", params={"version": 1}))
    assert _limited() == before + 3
    # Reading goes on.
    assert (await mod.get(f"/api/spaces/{team.id}/calendars")).status_code == 200
    assert (await mod.get("/api/calendars")).status_code == 200


async def _other(make_client: Any, email: str) -> AsyncClient:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, email)
    return client


async def test_making_events_counts_reading_them_does_not(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    moderator = await make_user()
    team = await make_space("team", members=[(moderator, "moderator")])
    mod = await _other(make_client, moderator.email)
    calendar = await new_calendar(mod, team.id, "Termine")
    monkeypatch.setattr(get_settings(), "write_rate_per_minute", 2)
    made = await new_event(mod, calendar["id"])  # the calendar and this: 2
    for _ in range(3):
        assert (await mod.get(f"/api/events/{made['id']}")).status_code == 200
        r = await mod.get(
            "/api/calendar/events",
            params={"from": "2026-11-23T00:00:00Z", "to": "2026-11-24T00:00:00Z"},
        )
        assert r.status_code == 200
    _refused(
        await mod.post(
            f"/api/calendars/{calendar['id']}/events",
            json={
                "title": "X",
                "starts_at": "2026-11-23T10:00:00Z",
                "ends_at": "2026-11-23T11:00:00Z",
            },
        )
    )


async def test_changing_and_deleting_events_count(
    make_client: Any, make_user: MakeUser, make_space: MakeSpace, monkeypatch: pytest.MonkeyPatch
) -> None:
    moderator = await make_user()
    team = await make_space("team", members=[(moderator, "moderator")])
    mod = await _other(make_client, moderator.email)
    made = await new_event(mod, (await new_calendar(mod, team.id, "Termine"))["id"])
    monkeypatch.setattr(get_settings(), "write_rate_per_minute", 3)  # 2 so far, a change: 3
    changed = await mod.patch(f"/api/events/{made['id']}", json={"version": 1, "title": "Y"})
    assert changed.status_code == 200, changed.text
    _refused(await mod.patch(f"/api/events/{made['id']}", json={"version": 2, "title": "Z"}))
    _refused(await mod.delete(f"/api/events/{made['id']}", params={"version": 2}))

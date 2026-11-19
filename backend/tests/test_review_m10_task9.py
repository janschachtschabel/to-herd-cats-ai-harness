"""Review of M10 task 9 (overlays): what the reviewer checked beyond the task's tests.
Red tests name their finding (R9-n); the others are guards that pass at 36954d7."""

import base64
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.spaces.repository import SpaceRepository
from tests.factories_agents import assign_default
from tests.factories_automations import placed
from tests.factories_overlays import (
    FROM,
    TO,
    URL,
    expect,
    new_channel,
    overlays,
    refs,
    set_scene,
)
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_writing import Work


def _cursor(*parts: str) -> str:
    return base64.urlsafe_b64encode(json.dumps(list(parts)).encode()).decode().rstrip("=")


ID = "00000000-0000-7000-8000-000000000000"


@pytest.mark.parametrize(
    "at",
    [
        "9999-12-31T23:59:59-01:00",  # past datetime's last year once read in UTC
        "0001-01-01T00:00:00+01:00",  # before its first
    ],
)
async def test_a_cursor_whose_term_leaves_datetimes_range_answers_422(work: Work, at: str) -> None:
    """R9-1: `_after` turns the cursor's term to UTC outside what it catches."""
    alice = work.bench.people.alice
    for kind in ("automations", "tickets"):
        cursor = _cursor("2026-11-20", kind, ID, "UTC", at)
        r = await alice.get(URL, params={"from": FROM, "to": TO, "cursor": cursor})
        assert (r.status_code, r.json()["error"]["code"]) == (422, "validation_failed"), kind


async def test_without_ai_use_tickets_and_sprints_show_and_no_automation(
    work: Work, make_space: MakeSpace
) -> None:
    scene = await set_scene(work, make_space)
    people = work.bench.people
    await assign_default(people.admin, None)  # nobody is assigned a model any more
    assert refs(await overlays(people.alice)) == expect(
        scene, "werk-ticket", "werk-sprint", "geheim-ticket"
    )
    only: list[dict[str, Any]] = await overlays(people.alice, kinds="automations")
    assert only == []


async def test_a_guest_sees_the_overlays_of_the_space_it_was_let_into(
    work: Work, make_space: MakeSpace
) -> None:
    scene = await set_scene(work, make_space)
    people = work.bench.people
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(people.users["gast"].id), SpaceRole.VIEWER
    )
    assert refs(await overlays(people.gast)) == expect(scene, "werk-ticket", "werk-sprint")


async def test_pages_hold_across_a_doubled_hour_before_midnight(work: Work) -> None:
    """Africa/Cairo, 28 October 2027: at 24:00 the clocks go back to 23:00, so the
    day's last hour comes twice and the next day begins an hour late."""
    bench, admin, alice = work.bench, work.bench.people.admin, work.bench.people.alice
    channel = await new_channel(admin, work.space.id, "takt")
    first = datetime(2027, 10, 28, 19, 30, tzinfo=UTC)  # 22:30 EEST
    for step in range(8):  # 22:30, 23:00, 23:30 | 23:00, 23:30 again | 00:00, 00:30, 01:00
        await placed(bench, channel, due=first + timedelta(minutes=30 * step))
    for day in ("2027-10-28", "2027-10-29"):
        await new_ticket(admin, work.space.id, f"t{day}", due_on=day)
    span: dict[str, Any] = {"from": "2027-10-28", "to": "2027-10-30", "time_zone": "Africa/Cairo"}
    whole = await overlays(alice, **span)
    days = [i["starts_on"] for i in whole if i["kind"] == "automations"]
    assert days == ["2027-10-28"] * 5 + ["2027-10-29"] * 3
    assert len(whole) == 10
    for limit in (1, 2, 3):
        assert await overlays(alice, limit=limit, **span) == whole, limit
    one_day = await overlays(alice, **{**span, "to": "2027-10-29"})
    assert one_day == [i for i in whole if i["starts_on"] == "2027-10-28"]

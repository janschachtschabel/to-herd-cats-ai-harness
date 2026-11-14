"""Lists of automations (plan M7 decision 14): "mine", per agent (`agent.manage`), per
space (what the caller may see there), each item with its next term, state and last
run; and the log of one automation, paginated, newest term first."""

import uuid
from datetime import timedelta
from typing import Any

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.automations.firing import fire_next
from app.modules.automations.models import Automation
from app.modules.spaces.repository import SpaceRepository
from tests.factories_automations import finish_runs
from tests.factories_writing import Work
from tests.test_automation_api import BASE, DAILY, NOW, body, channel, clock, make, refused

__all__ = ["clock"]  # the fixture that sets the service's clock


async def items(client: Any, path: str) -> list[dict[str, Any]]:
    r = await client.get(path)
    assert r.status_code == 200, r.text
    found: list[dict[str, Any]] = r.json()["items"]
    return found


async def test_mine_lists_my_automations_newest_first_a_page_at_a_time(work: Work) -> None:
    alice = work.bench.people.alice
    made = [await make(alice, body(work, {"type": "dm"}, DAILY)) for _ in range(3)]
    first = await alice.get(f"{BASE}?limit=2")
    assert first.status_code == 200, first.text
    page = first.json()
    assert [a["id"] for a in page["items"]] == [made[2]["id"], made[1]["id"]]
    rest = await alice.get(f"{BASE}?limit=2&cursor={page['next_cursor']}")
    assert [a["id"] for a in rest.json()["items"]] == [made[0]["id"]]
    assert rest.json()["next_cursor"] is None
    assert await items(work.bench.people.bob, BASE) == []


async def test_an_item_shows_its_last_run_and_its_result(work: Work) -> None:
    bench = work.bench
    made = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    fired = await fire_next(bench.session, NOW + timedelta(days=1))
    assert fired is not None and fired.run_id is not None
    (item,) = await items(bench.people.alice, BASE)
    last = item["last_run"]
    assert (last["outcome"], last["run_id"], last["run_state"]) == (
        "started",
        str(fired.run_id),
        "queued",
    )
    assert last["stop_reason"] is None and last["heartbeat_ok"] is False
    assert item["next_due_at"] > made["next_due_at"]
    await finish_runs(bench.session)
    (item,) = await items(bench.people.alice, BASE)
    assert (item["last_run"]["run_state"], item["last_run"]["stop_reason"]) == ("done", "completed")


async def test_an_agents_automations_are_for_who_manages_agents(work: Work) -> None:
    bench = work.bench
    made = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    path = f"/api/agents/{bench.agent.id}/automations"
    assert [a["id"] for a in await items(bench.people.admin, path)] == [made["id"]]
    refused(await bench.people.alice.get(path), 404, "agent.not_found")
    refused(
        await bench.people.admin.get(f"/api/agents/{made['id']}/automations"),
        404,
        "agent.not_found",
    )


async def test_a_spaces_automations_are_those_the_caller_sees_there(work: Work) -> None:
    bench = work.bench
    alice, bob = bench.people.alice, bench.people.bob
    await make(alice, body(work, {"type": "dm"}, DAILY))
    place = {"type": "channel", "conversation_id": await channel(work)}
    in_space = await make(alice, body(work, place, DAILY))
    path = f"/api/spaces/{work.space.id}/automations"
    assert [a["id"] for a in await items(alice, path)] == [in_space["id"]]
    refused(await bob.get(path), 404, "space.not_found")
    bob_user = bench.people.users["bob"]
    spaces = SpaceRepository(bench.session)
    await spaces.set_member(work.space.id, Principal.user(bob_user.id), SpaceRole.EDITOR)
    assert await items(bob, path) == []  # a member who does not manage the space
    await spaces.set_member(work.space.id, Principal.user(bob_user.id), SpaceRole.ADMIN)
    (seen,) = await items(bob, path)
    assert seen["id"] == in_space["id"]
    assert seen["abilities"] == {
        "edit": False,
        "pause": True,
        "resume": False,
        "delete": True,
        "run": False,
        "take_over": True,
    }


async def test_the_log_shows_each_term_newest_first(work: Work) -> None:
    bench = work.bench
    made = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    first = await fire_next(bench.session, NOW + timedelta(days=1))
    second = await fire_next(bench.session, NOW + timedelta(days=2))  # still busy
    assert first is not None and second is not None
    path = f"{BASE}/{made['id']}/firings"
    r = await bench.people.alice.get(f"{path}?limit=1")
    assert r.status_code == 200, r.text
    (newest,) = r.json()["items"]
    assert (newest["outcome"], newest["run_id"], newest["heartbeat_ok"]) == (
        "skipped_busy",
        None,
        False,
    )
    rest = await bench.people.alice.get(f"{path}?limit=1&cursor={r.json()['next_cursor']}")
    (oldest,) = rest.json()["items"]
    assert (oldest["outcome"], oldest["run_id"]) == ("started", str(first.run_id))
    refused(await bench.people.bob.get(path), 404, "automation.not_found")


async def test_an_item_says_how_many_terms_in_a_row_could_not_fire(work: Work) -> None:
    """Set aside by the due loop (review M7, finding 3): the streak shows, so its owner
    sees that it keeps failing."""
    alice = work.bench.people.alice
    made = await make(alice, body(work, {"type": "dm"}, DAILY))
    assert made["term_errors"] == 0
    row = await work.bench.session.get(Automation, uuid.UUID(made["id"]))
    assert row is not None
    row.term_errors = 3
    await work.bench.session.flush()
    assert [a["term_errors"] for a in await items(alice, BASE)] == [3]

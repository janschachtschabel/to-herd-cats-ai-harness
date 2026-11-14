"""Daily budgets (spec 7.4, plan M7 decision 10), the administration: admins
(`ai.manage`) list, set and remove a limit for the organisation, a person or an agent,
in tokens and/or EUR per UTC day, each write naming the version it read (409); the
list shows today's use beside each budget. Anyone else gets 404 `ai.not_found`."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy import update

from app.modules.ai.models import UsageRecord
from app.modules.ai.usage import record_usage
from tests.factories_agents import Bench

BUDGETS = "/api/ai/budgets"


def _path(bench: Bench, scope: str) -> str:
    if scope == "organisation":
        return f"{BUDGETS}/organisation"
    if scope == "user":
        return f"{BUDGETS}/users/{bench.people.id('alice')}"
    return f"{BUDGETS}/agents/{bench.agent.id}"


async def put(bench: Bench, scope: str, status: int = 200, **body: Any) -> dict[str, Any]:
    r = await bench.people.admin.put(_path(bench, scope), json={"version": None, **body})
    assert r.status_code == status, r.text
    result: dict[str, Any] = r.json()
    return result


async def listed(bench: Bench) -> list[dict[str, Any]]:
    r = await bench.people.admin.get(BUDGETS)
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def use(
    bench: Bench, *, who: str = "alice", agent: bool = False, days_ago: int = 0, **kw: Any
) -> UsageRecord:
    """A call booked to `who` (and the agent), today or `days_ago`."""
    fields: dict[str, Any] = {"model": "m1", "tokens_in": 100, "tokens_out": 50, **kw}
    record = await record_usage(
        bench.session,
        org_id=bench.agent.org_id,
        connection_id=bench.connection.id,
        duration_ms=10,
        user_id=bench.people.users[who].id,
        agent_id=bench.agent.id if agent else None,
        **fields,
    )
    if days_ago:
        when = datetime.now(UTC) - timedelta(days=days_ago)
        await bench.session.execute(
            update(UsageRecord).where(UsageRecord.id == record.id).values(created_at=when)
        )
    return record


async def test_admins_set_list_and_remove_budgets(bench: Bench) -> None:
    org = await put(bench, "organisation", tokens_per_day=1_000_000)
    person = await put(bench, "user", cost_per_day="2.50")
    agent = await put(bench, "agent", tokens_per_day=5000, cost_per_day="1")
    assert (org["scope"], org["subject_id"], org["name"]) == ("organisation", None, None)
    assert (person["scope"], person["subject_id"], person["name"]) == (
        "user",
        bench.people.id("alice"),
        "Alice",
    )
    assert (agent["scope"], agent["name"], agent["tokens_per_day"]) == ("agent", "Ava", 5000)
    assert Decimal(person["cost_per_day"]) == Decimal("2.50") and person["tokens_per_day"] is None
    assert [b["id"] for b in await listed(bench)] == [org["id"], person["id"], agent["id"]]
    changed = await put(bench, "user", tokens_per_day=10, version=person["version"])
    assert changed["id"] == person["id"] and changed["version"] == person["version"] + 1
    assert (changed["tokens_per_day"], changed["cost_per_day"]) == (10, None)
    r = await bench.people.admin.delete(f"{BUDGETS}/{agent['id']}", params={"version": 1})
    assert r.status_code == 204, r.text
    assert [b["scope"] for b in await listed(bench)] == ["organisation", "user"]


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"tokens_per_day": None, "cost_per_day": None},
        {"tokens_per_day": 0},
        {"tokens_per_day": -5},
        {"cost_per_day": "0"},
        {"cost_per_day": "1.234"},
        {"cost_per_day": "x"},
        {"tokens_per_day": 10**13},
    ],
)
async def test_a_budget_needs_a_sane_limit(bench: Bench, body: dict[str, Any]) -> None:
    await put(bench, "organisation", 422, **body)


async def test_writes_name_the_version(bench: Bench) -> None:
    made = await put(bench, "agent", tokens_per_day=100)
    again = await put(bench, "agent", 409, tokens_per_day=200)
    assert again["error"]["code"] == "ai.budget_version_conflict"
    assert again["error"]["details"]["current_version"] == made["version"]
    stale = await put(bench, "agent", 409, tokens_per_day=200, version=made["version"] + 1)
    assert stale["error"]["code"] == "ai.budget_version_conflict"
    r = await bench.people.admin.delete(f"{BUDGETS}/{made['id']}", params={"version": 7})
    assert r.status_code == 409 and r.json()["error"]["code"] == "ai.budget_version_conflict"
    missing = await bench.people.admin.delete(f"{BUDGETS}/{uuid.uuid4()}", params={"version": 1})
    assert missing.status_code == 404 and missing.json()["error"]["code"] == "ai.budget_not_found"


async def test_the_subject_must_be_of_the_organisation(bench: Bench) -> None:
    admin, nobody = bench.people.admin, uuid.uuid4()
    body = {"tokens_per_day": 1, "version": None}
    user = await admin.put(f"{BUDGETS}/users/{nobody}", json=body)
    assert user.status_code == 404 and user.json()["error"]["code"] == "users.not_found"
    agent = await admin.put(f"{BUDGETS}/agents/{nobody}", json=body)
    assert agent.status_code == 404 and agent.json()["error"]["code"] == "agent.not_found"


async def test_people_without_ai_manage_learn_nothing(bench: Bench) -> None:
    made = await put(bench, "organisation", tokens_per_day=100)
    alice, body = bench.people.alice, {"tokens_per_day": 1, "version": None}
    answers = [
        await alice.get(BUDGETS),
        await alice.put(f"{BUDGETS}/organisation", json=body),
        await alice.put(f"{BUDGETS}/users/{bench.people.id('alice')}", json=body),
        await alice.put(f"{BUDGETS}/agents/{bench.agent.id}", json=body),
        await alice.delete(f"{BUDGETS}/{made['id']}", params={"version": 1}),
    ]
    for r in answers:
        assert r.status_code == 404 and r.json()["error"]["code"] == "ai.not_found", r.text


async def test_the_list_pages(bench: Bench) -> None:
    for scope in ("organisation", "user", "agent"):
        await put(bench, scope, tokens_per_day=100)
    first = (await bench.people.admin.get(BUDGETS, params={"limit": 2})).json()
    rest = (
        await bench.people.admin.get(BUDGETS, params={"limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert [b["scope"] for b in first["items"] + rest["items"]] == ["organisation", "user", "agent"]
    assert rest["next_cursor"] is None


async def test_the_list_shows_todays_use(bench: Bench) -> None:
    bench.connection.prices = {"m1": {"input": "1000", "output": "1000"}}  # EUR per M tokens
    await bench.session.flush()
    await put(bench, "organisation", tokens_per_day=1000)
    await put(bench, "user", cost_per_day="0.30")
    await put(bench, "agent", tokens_per_day=150)
    await use(bench, agent=True)  # Alice through Ava: 150 tokens, 0.15 EUR
    await use(bench, who="bob", model="m2")  # no price: tokens only
    await use(bench, tokens_in=10_000, days_ago=1)  # yesterday's does not count
    today = {b["scope"]: b["today"] for b in await listed(bench)}
    assert today["organisation"]["tokens"] == 300 and today["organisation"]["unpriced_calls"] == 1
    assert Decimal(today["organisation"]["cost"]) == Decimal("0.15")
    assert (today["user"]["tokens"], Decimal(today["user"]["cost"])) == (150, Decimal("0.15"))
    assert today["user"]["exhausted"] is False and today["organisation"]["exhausted"] is False
    assert today["agent"]["tokens"] == 150 and today["agent"]["exhausted"] is True

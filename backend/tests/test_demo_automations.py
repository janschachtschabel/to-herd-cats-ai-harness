"""The demo's automations (scripts/demo_automations.py), with the OpenAI stub as the
model, on top of the agents of `scripts/demo_ai.py` (the `demo` fixture of
`test_demo_ai.py`: the runs run in the test's transaction): a daily summary in a
channel with one term run, a heartbeat whose term answered `HEARTBEAT_OK` and left
nothing, an event rule with a tag, a paused automation, budgets for the organisation
and an agent, and Team Nord's review interval."""

from typing import Any

from httpx import AsyncClient

from scripts import demo_ai, demo_automations
from tests.test_demo_ai import _get, demo  # noqa: F401 -- the fixture


async def _firings(client: AsyncClient, automation_id: str) -> list[dict[str, Any]]:
    return (await _get(client, f"/api/automations/{automation_id}/firings?limit=100"))["items"]


async def test_a_daily_summary_with_its_term_in_the_channel(demo: dict[str, Any]) -> None:  # noqa: F811
    seeded, anna = demo["seeded"], demo["clients"]["anna"]
    made = seeded.automations
    assert made is not None
    summary = await _get(anna, f"/api/automations/{made.ids['summary']}")
    assert (summary["kind"], summary["cron"], summary["time_zone"]) == (
        "recurring",
        "0 8 * * 1-5",
        "Europe/Berlin",
    )
    assert summary["agent"]["id"] == seeded.ai.agents["otto"]
    assert summary["place"]["conversation_id"] == seeded.channels["team-nord"]
    (term,) = await _firings(anna, made.ids["summary"])
    assert (term["outcome"], term["run_id"]) == ("started", made.runs["summary"])
    path = f"/api/conversations/{seeded.channels['team-nord']}/messages?limit=100"
    entries = [m for m in (await _get(anna, path))["items"] if m["kind"] == "system"]
    (entry,) = [m for m in entries if m["system"]["automation_id"] == made.ids["summary"]]
    replies = await _get(anna, f"/api/messages/{entry['id']}/replies?limit=100")
    assert [m["body_md"] for m in replies["items"]] == [demo_automations.SUMMARY]
    assert summary["instruction"] not in str(entries)  # the entry, not the instruction


async def test_a_silent_heartbeat_an_event_rule_and_a_paused_one(demo: dict[str, Any]) -> None:  # noqa: F811
    seeded, people, admin = demo["seeded"], demo["clients"], demo["admin"]
    made = seeded.automations
    beat = await _get(people["ben"], f"/api/automations/{made.ids['heartbeat']}")
    assert (beat["kind"], beat["interval_minutes"], beat["active_days"]) == (
        "heartbeat",
        60,
        [1, 2, 3, 4, 5],
    )
    assert beat["instruction"] == demo_automations.CHECKLIST
    (term,) = await _firings(people["ben"], made.ids["heartbeat"])
    assert (term["outcome"], term["heartbeat_ok"]) == ("started", True)
    dm = beat["place"]["conversation_id"]
    assert dm == seeded.ai.dms["ben_hilda"]
    said = await _get(people["ben"], f"/api/conversations/{dm}/messages?limit=100")
    assert [m["body_md"] for m in said["items"] if m["kind"] == "agent"] == [demo_ai.LEAVE_ANSWER]

    rule = await _get(admin, f"/api/automations/{made.ids['rule']}")
    tags = await _get(admin, f"/api/tags?space_id={seeded.space_id}&limit=100")
    kranich = next(t["id"] for t in tags["items"] if t["name"] == "kranich")
    assert (rule["kind"], rule["event_type"], rule["filter_tag_id"]) == (
        "event",
        "ticket.created",
        kranich,
    )
    assert rule["place"]["conversation_id"] == seeded.channels["projekt-kranich"]
    assert await _firings(admin, made.ids["rule"]) == []

    paused = await _get(people["anna"], f"/api/automations/{made.ids['paused']}")
    assert (paused["state"], paused["paused_reason"]) == ("paused", "manual")
    mine = await _get(people["anna"], "/api/automations?limit=100")
    assert {a["id"] for a in mine["items"]} == {made.ids["summary"], made.ids["paused"]}


async def test_budgets_and_the_review_interval(demo: dict[str, Any]) -> None:  # noqa: F811
    seeded, admin = demo["seeded"], demo["admin"]
    made = seeded.automations
    budgets = {b["id"]: b for b in (await _get(admin, "/api/ai/budgets?limit=100"))["items"]}
    organisation = budgets[made.budgets["organisation"]]
    assert (organisation["scope"], organisation["tokens_per_day"]) == ("organisation", 2_000_000)
    assert organisation["cost_per_day"] == "25.00"
    otto = budgets[made.budgets["otto"]]
    assert (otto["scope"], otto["subject_id"], otto["tokens_per_day"]) == (
        "agent",
        seeded.ai.agents["otto"],
        200_000,
    )
    assert otto["today"]["tokens"] > 0  # the summary's run counted
    space = await _get(admin, f"/api/spaces/{seeded.space_id}")
    assert space["review_interval_days"] == demo_automations.REVIEW_DAYS

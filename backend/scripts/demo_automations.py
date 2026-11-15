"""Automations in the demo (M7), in "Team Nord", through the public API, after the
agents of `demo_ai.py` (the same gate: only with a model):

- Anna's daily summary: Otto, every working day at 08:00 (Europe/Berlin), in
  #team-nord; run once now, so its log has a term and the channel its thread;
- Ben's heartbeat: Hilda, every 60 minutes on working days 08:00–18:00, in Ben's
  direct message with her, with a checklist; run once now, answering `HEARTBEAT_OK`:
  the log says so, nothing is delivered;
- the admin's event rule (event rules need the space's management): Otto, on
  `ticket.created` with the tag „kranich", in #projekt-kranich, quiet time 5 minutes;
- Anna's weekly reminder with Otto in her direct message, paused by hand;
- budgets: the organisation (2,000,000 tokens and 25.00 EUR a day) and Otto
  (200,000 tokens a day);
- a review interval of 90 days for Team Nord.

A page whose review is due cannot be made through the public API in real time:
publishing counts as a review, and the shortest interval is 7 days. The logged demo
(`docs/demo/m7.md`) moves the clock of its processes for that.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from scripts.demo_ai_model import Ai
from scripts.demo_api import DemoFailed, call

Clients = dict[str, httpx.AsyncClient]
ZONE = "Europe/Berlin"
SUMMARY = (
    "Gestern in Team Nord: eine neue Seite „Urlaub“, zwei Tickets in Arbeit, keine offene Frage."
)
CHECKLIST = """- Gibt es neue Fragen zum Urlaub im Handbuch?
- Steht in #team-nord eine Frage ohne Antwort?"""
REVIEW_DAYS = 90


@dataclass
class SeededAutomations:
    ids: dict[str, str] = field(default_factory=dict)  # summary, heartbeat, rule, paused
    runs: dict[str, str] = field(default_factory=dict)  # summary, heartbeat
    budgets: dict[str, str] = field(default_factory=dict)  # organisation, otto


async def _make(
    client: httpx.AsyncClient, agent_id: str, place: Any, text: str, schedule: Any
) -> str:
    body = {"agent_id": agent_id, "place": place, "instruction": text, "schedule": schedule}
    return str((await call(client, "POST", "/api/automations", body))["id"])


async def _run_now(
    client: httpx.AsyncClient, automation_id: str, ai: Ai, reply: str, wait_seconds: float
) -> str:
    """Runs the automation now (the stub answers `reply`) and waits until its run has
    ended (DemoFailed after `wait_seconds`; 0 checks once)."""
    if ai.script is not None:
        await ai.script([{"content": reply}])
    ran = await call(client, "POST", f"/api/automations/{automation_id}/run")
    term = ran["last_run"]
    if term is None or term["outcome"] != "started":
        raise DemoFailed(f"an automation did not start: {term and term['outcome']}")
    run_id = str(term["run_id"])
    deadline = time.monotonic() + wait_seconds
    while True:
        await ai.work()
        if (await call(client, "GET", f"/api/runs/{run_id}"))["state"] == "done":
            return run_id
        if time.monotonic() >= deadline:
            raise DemoFailed("an automation's run did not end: is the worker running?")
        await asyncio.sleep(0.5)


async def _budgets(admin: httpx.AsyncClient, otto: str, made: SeededAutomations) -> None:
    body = {"tokens_per_day": 2_000_000, "cost_per_day": "25.00", "version": None}
    made.budgets["organisation"] = str(
        (await call(admin, "PUT", "/api/ai/budgets/organisation", body))["id"]
    )
    body = {"tokens_per_day": 200_000, "version": None}
    made.budgets["otto"] = str(
        (await call(admin, "PUT", f"/api/ai/budgets/agents/{otto}", body))["id"]
    )


async def build(
    admin: httpx.AsyncClient,
    people: Clients,
    *,
    ai: Ai,
    agents: dict[str, str],
    space_id: str,
    channels: dict[str, str],
    wait_seconds: float = 60,
) -> SeededAutomations:
    made = SeededAutomations()
    anna, ben = people["anna"], people["ben"]
    hilda, otto = agents["hilda"], agents["otto"]
    await _budgets(admin, otto, made)

    team = {"type": "channel", "conversation_id": channels["team-nord"]}
    weekdays = {"kind": "recurring", "cron": "0 8 * * 1-5", "time_zone": ZONE}
    summary = (
        "Fasse zusammen, was gestern in Team Nord geschah: neue Seiten, Tickets, offene Fragen."
    )
    made.ids["summary"] = await _make(anna, otto, team, summary, weekdays)
    made.runs["summary"] = await _run_now(anna, made.ids["summary"], ai, SUMMARY, wait_seconds)

    beat = {
        "kind": "heartbeat",
        "interval_minutes": 60,
        "active_days": [1, 2, 3, 4, 5],
        "active_from": "08:00",
        "active_until": "18:00",
        "time_zone": ZONE,
    }
    made.ids["heartbeat"] = await _make(ben, hilda, {"type": "dm"}, CHECKLIST, beat)
    made.runs["heartbeat"] = await _run_now(
        ben, made.ids["heartbeat"], ai, "HEARTBEAT_OK", wait_seconds
    )

    tags = (await call(admin, "GET", f"/api/tags?space_id={space_id}&limit=100"))["items"]
    kranich = next(t["id"] for t in tags if t["name"] == "kranich")
    rule = {
        "kind": "event",
        "event_type": "ticket.created",
        "quiet_seconds": 300,
        "filter_tag_id": kranich,
    }
    place = {"type": "channel", "conversation_id": channels["projekt-kranich"]}
    text = "Prüfe jedes neue Kranich-Ticket: Fehlt eine Beschreibung oder ein Termin, frag nach."
    made.ids["rule"] = await _make(admin, otto, place, text, rule)

    friday = {"kind": "recurring", "cron": "0 16 * * 5", "time_zone": ZONE}
    reminder = "Erinnere mich an die Zeiterfassung der Woche."
    made.ids["paused"] = await _make(anna, otto, {"type": "dm"}, reminder, friday)
    path = f"/api/automations/{made.ids['paused']}"
    version = (await call(anna, "GET", path))["version"]
    await call(anna, "POST", f"{path}/pause", {"version": version})

    space = await call(admin, "GET", f"/api/spaces/{space_id}")
    body = {"review_interval_days": REVIEW_DAYS, "version": space["version"]}
    await call(admin, "PATCH", f"/api/spaces/{space_id}", body)
    return made

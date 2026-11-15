"""Agents at work in the demo (M6), in "Team Nord", through the public API: the
connection "Demo-Modell" with the standard assignment (Clara has no AI), two agents
(Hilda, level 1, viewer; Otto, level 2, editor, with the space's skill „protokoll"),
Ben's conversation with Hilda and her answer, a ticket Anna assigns to Otto that he
works up to „Zur Prüfung", Otto's open proposal for „Handbuch", his memory page
(asked in the thread of „Handbuch"), and a pending approval for Ben.

How the demo gets a model (`Ai`, `from_env`): `demo_ai_model.py`."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from scripts.demo_ai_model import Ai, from_env
from scripts.demo_api import DemoFailed, call, post

__all__ = ["Ai", "DemoFailed", "SeededAi", "build", "from_env"]

Clients = dict[str, httpx.AsyncClient]
SKILL = """# Protokoll

Protokolle beginnen mit Datum, Anwesenden und Thema. Danach je Punkt: was besprochen
wurde, was entschieden wurde, wer was bis wann tut.
"""
TICKET = "Protokoll der Teamrunde schreiben"
LEAVE_ANSWER = "Es gibt 30 Tage im Jahr, Teilzeit anteilig. Anträge zwei Wochen vorher abstimmen."
TICKET_ANSWER = "Das Protokoll folgt der Vorlage „protokoll“. Bitte prüfen."
MEMORY = "- Anna Nord moderiert Team Nord; Fragen zum Urlaub beantwortet die Seite „Urlaub“."
HANDBOOK_PROPOSAL = """# Handbuch

Wie wir im Team Nord arbeiten. Fragen gern in **#team-nord** oder in der Diskussion
einer Seite. Protokolle folgen der Vorlage „protokoll“.

- [[Urlaub]]
"""
LEAVE_PROPOSAL = """# Urlaub

- 30 Tage im Jahr, Teilzeit anteilig.
- Anträge zwei Wochen vorher im Team abstimmen.
- Resturlaub verfällt am 31. März des Folgejahres.
"""


@dataclass
class SeededAi:
    connection_id: str = ""
    agents: dict[str, str] = field(default_factory=dict)  # ids: hilda, otto
    skill_id: str = ""
    dms: dict[str, str] = field(default_factory=dict)  # ben_hilda, anna_otto, ben_otto
    ticket_number: int = 0
    runs: dict[str, str] = field(default_factory=dict)  # by step
    approval_id: str | None = None
    memory_page_id: str | None = None


def _calls(*calls: tuple[str, dict[str, Any]]) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": args} for name, args in calls]}


async def _setup(admin: httpx.AsyncClient, ai: Ai, ids: dict[str, str], space_id: str) -> SeededAi:
    made = SeededAi()
    connection = await call(admin, "POST", "/api/ai/connections", ai.connection_body())
    made.connection_id = str(connection["id"])
    version = (await call(admin, "GET", "/api/ai/assignments"))["version"]
    target = {"connection_id": made.connection_id, "model": ai.model}
    await call(admin, "PUT", "/api/ai/assignments/default", {"target": target, "version": version})
    no_ai = {"no_ai": True, "version": None}
    await call(admin, "PUT", f"/api/ai/assignments/users/{ids['clara']}", no_ai)
    for key, name, level, role, intro in (
        ("hilda", "Hilda", 1, "viewer", "Beantwortet Fragen aus dem Handbuch."),
        ("otto", "Otto", 2, "editor", "Schreibt Protokolle und pflegt das Handbuch."),
    ):
        agent = await call(
            admin,
            "POST",
            "/api/agents",
            {
                "name": name,
                "intro": intro,
                "instructions": "Arbeite sorgfältig und antworte kurz auf Deutsch.",
                "connection_id": made.connection_id,
                "model": ai.model,
                "responsible_user_id": ids["anna"],
                "status": "active",
                "level": level,
            },
        )
        made.agents[key] = str(agent["id"])
        member = {"member_type": "agent", "member_id": made.agents[key], "role": role}
        await call(admin, "PUT", f"/api/spaces/{space_id}/members", member)
    skill = await call(
        admin,
        "POST",
        "/api/skills",
        {
            "space_id": space_id,
            "name": "protokoll",
            "description": "Wie ein Protokoll im Team Nord aussieht.",
            "content": SKILL,
        },
    )
    made.skill_id = str(skill["id"])
    otto = await call(admin, "GET", f"/api/agents/{made.agents['otto']}")
    body = {"skill_ids": [made.skill_id], "version": otto["version"]}
    await call(admin, "PUT", f"/api/agents/{made.agents['otto']}/skills", body)
    return made


async def _newest(client: httpx.AsyncClient, agent_id: str) -> dict[str, Any] | None:
    runs = await call(client, "GET", f"/api/runs?agent_id={agent_id}&limit=1")
    return runs["items"][0] if runs["items"] else None


async def _step(
    client: httpx.AsyncClient,
    agent_id: str,
    ai: Ai,
    replies: list[dict[str, Any]],
    start: Callable[[], Awaitable[object]],
    wait_seconds: float,
) -> dict[str, Any]:
    """Scripts the stub (if any), starts a run with `start()` and waits until it has
    ended or waits for someone (DemoFailed after `wait_seconds`; 0 checks once)."""
    before = await _newest(client, agent_id)
    if ai.script is not None:
        await ai.script(replies)
    await start()
    deadline = time.monotonic() + wait_seconds
    while True:
        await ai.work()
        run = await _newest(client, agent_id)
        fresh = run is not None and (before is None or run["id"] != before["id"])
        if run is not None and fresh and run["state"] in ("done", "waiting"):
            return run
        if time.monotonic() >= deadline:
            raise DemoFailed("an agent's run did not end: is the worker running?")
        await asyncio.sleep(0.5)


async def _dm(client: httpx.AsyncClient, agent_id: str) -> str:
    return str((await call(client, "POST", "/api/dms", {"agent_id": agent_id}))["id"])


async def build(
    admin: httpx.AsyncClient,
    people: Clients,
    *,
    ai: Ai,
    ids: dict[str, str],
    space_id: str,
    handbook_id: str,
    leave_id: str,
    wait_seconds: float = 60,
) -> SeededAi:
    made = await _setup(admin, ai, ids, space_id)
    hilda, otto = made.agents["hilda"], made.agents["otto"]
    anna, ben = people["anna"], people["ben"]
    made.dms = {
        "ben_hilda": await _dm(ben, hilda),
        "anna_otto": await _dm(anna, otto),
        "ben_otto": await _dm(ben, otto),
    }

    def ask(client: httpx.AsyncClient, dm: str, text: str) -> Callable[[], Awaitable[str]]:
        return lambda: post(client, made.dms[dm], text)

    replies = [_calls(("read_page", {"page_id": leave_id})), {"content": LEAVE_ANSWER}]
    start = ask(ben, "ben_hilda", "Wie viele Urlaubstage habe ich?")
    made.runs["answer"] = (await _step(ben, hilda, ai, replies, start, wait_seconds))["id"]

    made.runs["ticket"] = await _ticket(anna, made, ai, space_id, wait_seconds)

    change = {"page_id": handbook_id, "content_md": HANDBOOK_PROPOSAL, "reason": "Vorlage nennen"}
    replies = [_calls(("propose_page_change", change)), {"content": "Vorschlag ist gemacht."}]
    start = ask(anna, "anna_otto", "Nenne im Handbuch bitte die Protokollvorlage.")
    made.runs["proposal"] = (await _step(anna, otto, ai, replies, start, wait_seconds))["id"]

    memory = {"space_id": space_id, "content": MEMORY}  # asked where Team Nord reads
    replies = [_calls(("update_memory", memory)), {"content": "Gemerkt."}]
    thread = str((await call(anna, "GET", f"/api/pages/{handbook_id}/thread"))["id"])
    remember = "@Otto merk dir bitte, wer Team Nord moderiert."
    start = lambda: post(anna, thread, remember, mentions=(otto,))  # noqa: E731
    made.runs["memory"] = (await _step(anna, otto, ai, replies, start, wait_seconds))["id"]
    made.memory_page_id = await _memory_page(anna, space_id)

    await _confirm(admin, otto, "propose_page_change")
    change = {"page_id": leave_id, "content_md": LEAVE_PROPOSAL, "reason": "Verfall ergänzen"}
    start = ask(ben, "ben_otto", "Ergänze bitte, wann Resturlaub verfällt.")
    replies = [_calls(("propose_page_change", change))]
    run = await _step(ben, otto, ai, replies, start, wait_seconds)
    made.runs["approval"] = str(run["id"])
    pending = await call(ben, "GET", "/api/approvals?state=pending&limit=100")
    found = [a for a in pending["items"] if a["run_id"] == run["id"]]
    made.approval_id = str(found[0]["id"]) if found else None
    return made


async def _ticket(
    anna: httpx.AsyncClient, made: SeededAi, ai: Ai, space_id: str, wait_seconds: float
) -> str:
    statuses = (await call(anna, "GET", f"/api/spaces/{space_id}/ticket-statuses"))["items"]
    review = next(s for s in statuses if s["category"] == "review")
    ticket = await call(
        anna,
        "POST",
        f"/api/spaces/{space_id}/tickets",
        {"title": TICKET, "description_md": "Die Teamrunde vom Montag festhalten."},
    )
    made.ticket_number = int(ticket["number"])
    key = f"HC-{ticket['number']}"
    replies = [
        _calls(("load_skill", {"name": "protokoll"})),
        _calls(("set_ticket_status", {"key": key, "status": review["name"]})),
        {"content": TICKET_ANSWER},
    ]
    assignee = {"type": "agent", "id": made.agents["otto"]}
    body = {"version": ticket["version"], "assignee": assignee}

    async def assign() -> object:
        return await call(anna, "PATCH", f"/api/tickets/{ticket['number']}", body)

    run = await _step(anna, made.agents["otto"], ai, replies, assign, wait_seconds)
    return str(run["id"])


async def _confirm(admin: httpx.AsyncClient, agent_id: str, tool: str) -> None:
    agent = await call(admin, "GET", f"/api/agents/{agent_id}")
    body = {"tools": [{"tool": tool, "policy": "confirm"}], "version": agent["version"]}
    await call(admin, "PUT", f"/api/agents/{agent_id}/tools", body)


async def _memory_page(client: httpx.AsyncClient, space_id: str) -> str | None:
    tree = await call(client, "GET", f"/api/spaces/{space_id}/pages/tree?limit=100")
    found = [
        p
        for p in tree["items"]
        if p["path"].startswith("_agenten/") and p["path"].endswith("/gedaechtnis")
    ]
    return str(found[0]["id"]) if found else None

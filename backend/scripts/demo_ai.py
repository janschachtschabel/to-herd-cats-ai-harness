"""Agents at work in the demo (M6), in "Team Nord", through the public API: the
connection "Demo-Modell" with the standard assignment (Clara has no AI), two agents
(Hilda, level 1, viewer; Otto, level 2, editor, with the space's skill „protokoll"),
Ben's conversation with Hilda and her answer, a ticket Anna assigns to Otto that he
works up to „Zur Prüfung", Otto's open proposal for „Handbuch", his memory page
(asked in the thread of „Handbuch"), and a pending approval for Ben.

How the demo gets a model (`from_env`): `HERD_DEMO_AI_KIND` turns it on (`local`, an
OpenAI-compatible endpoint the server reaches over http, such as the OpenAI stub of
the tests or a local model server; `openai`; `openai_compatible`), with
`HERD_DEMO_AI_URL` (its base URL; required except for `openai`), `HERD_DEMO_AI_MODEL`
(default `gpt-6-luna`) and `HERD_DEMO_AI_KEY_ENV` (the name of a `HERD_AI_*`
variable of the server that holds the key; the key itself never passes this
script). `HERD_DEMO_AI_STUB` is the stub's own address
(`python -m tests.support.openai_stub`): the demo then scripts the stub's replies
before every step, so every run ends as described. With a real model, the same
requests go out and the demo waits for each run to end, whatever the model did.
"""

import asyncio
import os
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from scripts.demo_api import DemoFailed, call, post

Script = Callable[[list[dict[str, Any]]], Awaitable[None]]
Clients = dict[str, httpx.AsyncClient]

KINDS = ("local", "openai", "openai_compatible")
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


async def _nothing() -> None:
    return None


@dataclass
class Ai:
    """The model of the demo. `script`: queues the stub's next replies (none: a real
    model answers); `work`: awaited before every look at a run (a no-op against a
    running installation, whose worker runs them)."""

    base_url: str | None = None
    kind: str = "local"
    model: str = "gpt-6-luna"
    key_env: str | None = None
    script: Script | None = None
    work: Callable[[], Awaitable[None]] = _nothing

    def connection_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"name": "Demo-Modell", "kind": self.kind, "models": [self.model]}
        if self.base_url:
            body["base_url"] = self.base_url
        if self.key_env:
            body["secret"] = {"env": self.key_env}
        return body


def _stub_script(control: str) -> Script:
    async def script(replies: list[dict[str, Any]]) -> None:
        async with httpx.AsyncClient(base_url=control) as stub:
            for path, body in (("/_stub/reset", None), ("/_stub/script", {"replies": replies})):
                response = await stub.post(path, json=body)
                if response.status_code != 200:
                    raise DemoFailed(f"stub {path}: {response.status_code}")

    return script


def from_env(env: Mapping[str, str] = os.environ) -> Ai | None:
    """The demo's model from the environment (module docstring); None: no AI demo."""
    kind = env.get("HERD_DEMO_AI_KIND", "")
    if not kind:
        return None
    url = env.get("HERD_DEMO_AI_URL") or None
    if kind not in KINDS or (url is None and kind != "openai"):
        raise DemoFailed(f"HERD_DEMO_AI_KIND {kind!r} needs one of {KINDS} and HERD_DEMO_AI_URL")
    stub = env.get("HERD_DEMO_AI_STUB")
    return Ai(
        base_url=url,
        kind=kind,
        model=env.get("HERD_DEMO_AI_MODEL") or "gpt-6-luna",
        key_env=env.get("HERD_DEMO_AI_KEY_ENV") or None,
        script=_stub_script(stub.rstrip("/")) if stub else None,
    )


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

"""Demo data for a fresh test installation (M1 to M4b), through the public API as the
browser uses it: three people, the team space "Team Nord" with two pages, two channels
with messages, thread replies, mentions and reactions, a direct message, a page
discussion that starts with the worker's system entries, and tickets (an epic with
stories, tasks and a bug in several statuses, assignments, tags, a linked page,
comments, a ticket key in a channel; see scripts/demo_tickets.py) and sprints (one
closed with its tally, one running, one planned, a backlog; scripts/demo_sprints.py);
with a model configured (`HERD_DEMO_AI_KIND`, see scripts/demo_ai_model.py) also agents at
work (M6) and automations and budgets (M7, scripts/demo_automations.py); MCP (M8,
scripts/demo_mcp.py): the switch on and Anna's read token, with a model an external
agent with a ticket waiting for pick-up, and with `--mcp-stub URL` a server on that
stub (never the outside network by default); sign-in (M9, scripts/demo_oidc.py): with
`--oidc-stub URL` only, an OIDC provider on that stub with self-registration for
demo.example (sign-ups wait for an admin's approval).

    cd backend && HERD_DEMO_ADMIN_PASSWORD=… HERD_DEMO_PASSWORD=… \\
        uv run python -m scripts.demo_seed --base http://127.0.0.1:8080 --admin admin@example.com \\
        [--mcp-stub https://localhost:8098/mcp] [--oidc-stub https://localhost:8100]

`HERD_DEMO_ADMIN_PASSWORD` is the admin's password, `HERD_DEMO_PASSWORD` (at least 10
characters) becomes the demo people's password. Passwords are read from the
environment only, never from arguments, and never printed. The worker must run (role
`all`, or a worker beside the API): the script waits up to 60 s for the page's system
entries (and then for the tickets'). A second run stops before changing anything (the
demo people exist).
"""

import argparse
import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

import httpx

from scripts import (
    demo_ai,
    demo_automations,
    demo_mcp,
    demo_messaging,
    demo_oidc,
    demo_sprints,
    demo_tickets,
)
from scripts.demo_api import DemoFailed, call
from scripts.demo_tickets import SeededTickets

Connect = Callable[[], Awaitable[httpx.AsyncClient]]

PEOPLE = {
    "anna": ("Anna Nord", "anna.nord@demo.example", "moderator"),
    "ben": ("Ben Berg", "ben.berg@demo.example", "editor"),
    "clara": ("Clara Klein", "clara.klein@demo.example", "viewer"),
}


class DemoExists(Exception):
    """The demo people exist already: the demo ran on this installation before."""


@dataclass
class Seeded:
    space_id: str = ""
    page_id: str = ""
    handbook_id: str = ""
    ids: dict[str, str] = field(default_factory=dict)
    emails: dict[str, str] = field(default_factory=dict)
    channels: dict[str, str] = field(default_factory=dict)
    dm_id: str = ""
    tickets: SeededTickets = field(default_factory=SeededTickets)
    sprints: dict[str, str] = field(default_factory=dict)  # ids by name
    ai: demo_ai.SeededAi | None = None
    automations: demo_automations.SeededAutomations | None = None
    mcp: demo_mcp.SeededMcp = field(default_factory=demo_mcp.SeededMcp)
    oidc: demo_oidc.SeededOidc = field(default_factory=demo_oidc.SeededOidc)


async def _login(connect: Connect, email: str, password: str) -> httpx.AsyncClient:
    client = await connect()
    await call(client, "POST", "/api/auth/login", {"email": email, "password": password})
    return client


async def _people(admin: httpx.AsyncClient, password: str, seeded: Seeded) -> None:
    for key, (name, email, _role) in PEOPLE.items():
        body = {"name": name, "email": email, "password": password, "system_role": "member"}
        response = await admin.post("/api/admin/users", json=body)
        if response.status_code == 409:
            raise DemoExists(email)
        if response.status_code != 201:
            raise DemoFailed(f"POST /api/admin/users: {response.status_code}")
        seeded.ids[key], seeded.emails[key] = str(response.json()["id"]), email


async def _space(admin: httpx.AsyncClient, seeded: Seeded) -> None:
    space = await call(admin, "POST", "/api/spaces", {"name": "Team Nord", "kind": "team"})
    seeded.space_id = str(space["id"])
    for key, (_name, _email, role) in PEOPLE.items():
        member = {"member_type": "user", "member_id": seeded.ids[key], "role": role}
        await call(admin, "PUT", f"/api/spaces/{seeded.space_id}/members", member)


async def _pages(anna: httpx.AsyncClient, seeded: Seeded) -> None:
    """Two published pages; the second is changed and restored, so its discussion gets
    three system entries (created, published, version restored)."""
    pages = f"/api/spaces/{seeded.space_id}/pages"
    handbook = await call(anna, "POST", pages, {"title": "Handbuch", "content_md": HANDBOOK})
    publish = {"version": handbook["version"]}
    await call(anna, "POST", f"/api/pages/{handbook['id']}/publish", publish)
    leave = await call(
        anna,
        "POST",
        pages,
        {"title": "Urlaub", "content_md": LEAVE, "parent_id": handbook["id"]},
    )
    seeded.handbook_id, page_id = str(handbook["id"]), str(leave["id"])
    publish = {"version": leave["version"]}
    leave = await call(anna, "POST", f"/api/pages/{page_id}/publish", publish)
    edit = {"content_md": LEAVE + "\nEntwurf: 35 Tage für alle.\n", "version": leave["version"]}
    leave = await call(anna, "PATCH", f"/api/pages/{page_id}", edit)
    restore = {"version": leave["version"]}
    await call(anna, "POST", f"/api/pages/{page_id}/versions/1/restore", restore)
    seeded.page_id = page_id


async def seed(
    connect: Connect,
    *,
    admin_email: str,
    admin_password: str,
    people_password: str,
    settle: Callable[[], Awaitable[None]],
    wait_seconds: float = 60,
    ai: demo_ai.Ai | None = None,
    mcp_stub: str | None = None,
    oidc_stub: str | None = None,
) -> Seeded:
    """Creates the demo. `connect()` gives a new client (own cookies, CSRF header) of
    the installation; `settle()` is awaited before the page discussion is used (a
    no-op against a running installation, whose worker writes the system entries);
    `ai`: the model for the agents (none: no agents); `mcp_stub`: an MCP server's
    address for the demo's server (none: no server); `oidc_stub`: an OIDC stub's issuer
    for the demo's sign-in provider (none: no provider)."""
    seeded = Seeded()
    admin = await _login(connect, admin_email, admin_password)
    await _people(admin, people_password, seeded)
    await _space(admin, seeded)
    people = {
        key: await _login(connect, email, people_password) for key, email in seeded.emails.items()
    }
    await _pages(people["anna"], seeded)
    await demo_messaging.channels(people, seeded)
    await demo_messaging.direct_message(people, seeded)
    await settle()
    await demo_messaging.discussion(people, seeded, wait_seconds)
    seeded.tickets = await demo_tickets.build(
        admin,
        people,
        space_id=seeded.space_id,
        page_id=seeded.page_id,
        ids=seeded.ids,
        channel_id=seeded.channels["projekt-kranich"],
    )
    seeded.sprints = await demo_sprints.build(
        people, space_id=seeded.space_id, seeded=seeded.tickets
    )
    await demo_tickets.comment(
        people, seeded.tickets, seeded.ids, settle=settle, wait_seconds=wait_seconds
    )
    if ai is not None:
        seeded.ai = await demo_ai.build(
            admin,
            people,
            ai=ai,
            ids=seeded.ids,
            space_id=seeded.space_id,
            handbook_id=seeded.handbook_id,
            leave_id=seeded.page_id,
            wait_seconds=wait_seconds,
        )
        seeded.automations = await demo_automations.build(
            admin,
            people,
            ai=ai,
            agents=seeded.ai.agents,
            space_id=seeded.space_id,
            channels=seeded.channels,
            wait_seconds=wait_seconds,
        )
    seeded.mcp = await demo_mcp.build(
        admin,
        people,
        ids=seeded.ids,
        space_id=seeded.space_id,
        with_agents=ai is not None,
        mcp_stub=mcp_stub,
    )
    seeded.oidc = await demo_oidc.build(admin, oidc_stub=oidc_stub)
    return seeded


HANDBOOK = """# Handbuch

Wie wir im Team Nord arbeiten. Fragen gern in **#team-nord** oder in der Diskussion
einer Seite.

- [[Urlaub]]
"""

LEAVE = """# Urlaub

- 30 Tage im Jahr, Teilzeit anteilig.
- Anträge zwei Wochen vorher im Team abstimmen.
"""


async def _main(base: str, admin_email: str, mcp_stub: str | None, oidc_stub: str | None) -> int:
    admin_password = os.environ.get("HERD_DEMO_ADMIN_PASSWORD", "")
    people_password = os.environ.get("HERD_DEMO_PASSWORD", "")
    if not admin_password or len(people_password) < 10:
        print("set HERD_DEMO_ADMIN_PASSWORD and HERD_DEMO_PASSWORD (≥ 10 characters)")
        return 2
    clients: list[httpx.AsyncClient] = []

    async def connect() -> httpx.AsyncClient:
        client = httpx.AsyncClient(base_url=base, headers={"X-Requested-With": "herd"})
        clients.append(client)
        return client

    async def nothing() -> None:
        return None

    try:
        ai = demo_ai.from_env()
        seeded = await seed(
            connect,
            admin_email=admin_email,
            admin_password=admin_password,
            people_password=people_password,
            settle=nothing,
            ai=ai,
            mcp_stub=mcp_stub,
            oidc_stub=oidc_stub,
        )
    except DemoExists as exists:
        print(f"demo data present already ({exists}); nothing changed")
        return 1
    except DemoFailed as failed:
        print(f"demo failed: {failed}")
        return 1
    finally:
        for client in clients:
            await client.aclose()
    people = ", ".join(seeded.emails.values())
    tickets = len(seeded.tickets.numbers)
    sprints = len(seeded.sprints)
    print(
        f"demo ready: space Team Nord ({seeded.space_id}), {tickets} tickets, "
        f"{sprints} sprints, people {people}"
        + (f", agents Hilda and Otto (ticket HC-{seeded.ai.ticket_number})" if seeded.ai else "")
        + (f", {len(seeded.automations.ids)} automations" if seeded.automations else "")
        + ", MCP on with Anna's read token"
        + (
            f", external agent Pipeline (ticket HC-{seeded.mcp.ticket_number} waiting for pick-up)"
            if seeded.mcp.agent_id
            else ""
        )
        + (f", MCP server {demo_mcp.SERVER}" if seeded.mcp.server_id else "")
        + (
            f", sign-in {demo_oidc.NAME} (sign-up for {demo_oidc.DOMAIN})"
            if seeded.oidc.provider_id
            else ""
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--admin", required=True, help="the admin's email")
    parser.add_argument(
        "--mcp-stub", help="an MCP server's address (a stub) for the demo's server; none: none"
    )
    parser.add_argument(
        "--oidc-stub", help="an OIDC stub's issuer for the demo's sign-in provider; none: none"
    )
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.base.rstrip("/"), args.admin, args.mcp_stub, args.oidc_stub))


if __name__ == "__main__":
    sys.exit(main())

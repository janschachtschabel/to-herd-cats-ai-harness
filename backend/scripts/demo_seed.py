"""Demo data for a fresh test installation (M1 to M3), through the public API as the
browser uses it: three people, the team space "Team Nord" with two pages, two channels
with messages, thread replies, mentions and reactions, a direct message, and a page
discussion that starts with the worker's system entries.

    cd backend && HERD_DEMO_ADMIN_PASSWORD=… HERD_DEMO_PASSWORD=… \\
        uv run python -m scripts.demo_seed --base http://127.0.0.1:8080 --admin admin@example.com

`HERD_DEMO_ADMIN_PASSWORD` is the admin's password, `HERD_DEMO_PASSWORD` (at least 10
characters) becomes the demo people's password. Passwords are read from the
environment only, never from arguments, and never printed. The worker must run (role
`all`, or a worker beside the API): the script waits up to 60 s for the page's system
entries. A second run stops before changing anything (the demo people exist).
"""

import argparse
import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

Connect = Callable[[], Awaitable[httpx.AsyncClient]]

PEOPLE = {
    "anna": ("Anna Nord", "anna.nord@demo.example", "moderator"),
    "ben": ("Ben Berg", "ben.berg@demo.example", "editor"),
    "clara": ("Clara Klein", "clara.klein@demo.example", "viewer"),
}
SYSTEM_ENTRIES = 3  # page.created, page.published, page.version_restored


class DemoExists(Exception):
    """The demo people exist already: the demo ran on this installation before."""


class DemoFailed(Exception):
    """The API refused a step (status and error code in the message)."""


@dataclass
class Seeded:
    space_id: str = ""
    page_id: str = ""
    ids: dict[str, str] = field(default_factory=dict)
    emails: dict[str, str] = field(default_factory=dict)
    channels: dict[str, str] = field(default_factory=dict)
    dm_id: str = ""


async def _call(client: httpx.AsyncClient, method: str, path: str, body: Any = None) -> Any:
    response = await client.request(method, path, json=body)
    if response.status_code >= 300:
        code = response.json().get("error", {}).get("code") if response.content else None
        raise DemoFailed(f"{method} {path}: {response.status_code} {code}")
    return response.json() if response.content else None


async def _login(connect: Connect, email: str, password: str) -> httpx.AsyncClient:
    client = await connect()
    await _call(client, "POST", "/api/auth/login", {"email": email, "password": password})
    return client


def mention(name: str, user_id: str) -> str:
    """A mention as the composer writes it (`@[Name](user:<id>)`)."""
    return f"@[{name}](user:{user_id})"


async def _post(
    client: httpx.AsyncClient,
    conversation_id: str,
    body_md: str,
    *,
    parent_id: str | None = None,
    mentions: tuple[str, ...] = (),
) -> str:
    body = {"body_md": body_md, "parent_id": parent_id, "mentions": list(mentions)}
    message = await _call(client, "POST", f"/api/conversations/{conversation_id}/messages", body)
    return str(message["id"])


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
    space = await _call(admin, "POST", "/api/spaces", {"name": "Team Nord", "kind": "team"})
    seeded.space_id = str(space["id"])
    for key, (_name, _email, role) in PEOPLE.items():
        member = {"member_type": "user", "member_id": seeded.ids[key], "role": role}
        await _call(admin, "PUT", f"/api/spaces/{seeded.space_id}/members", member)


async def _pages(anna: httpx.AsyncClient, seeded: Seeded) -> None:
    """Two published pages; the second is changed and restored, so its discussion gets
    three system entries (created, published, version restored)."""
    pages = f"/api/spaces/{seeded.space_id}/pages"
    handbook = await _call(anna, "POST", pages, {"title": "Handbuch", "content_md": HANDBOOK})
    publish = {"version": handbook["version"]}
    await _call(anna, "POST", f"/api/pages/{handbook['id']}/publish", publish)
    leave = await _call(
        anna,
        "POST",
        pages,
        {"title": "Urlaub", "content_md": LEAVE, "parent_id": handbook["id"]},
    )
    page_id = str(leave["id"])
    publish = {"version": leave["version"]}
    leave = await _call(anna, "POST", f"/api/pages/{page_id}/publish", publish)
    edit = {"content_md": LEAVE + "\nEntwurf: 35 Tage für alle.\n", "version": leave["version"]}
    leave = await _call(anna, "PATCH", f"/api/pages/{page_id}", edit)
    restore = {"version": leave["version"]}
    await _call(anna, "POST", f"/api/pages/{page_id}/versions/1/restore", restore)
    seeded.page_id = page_id


async def _channels(people: dict[str, httpx.AsyncClient], seeded: Seeded) -> None:
    anna, ben, clara = people["anna"], people["ben"], people["clara"]
    channels = f"/api/spaces/{seeded.space_id}/channels"
    for name, topic in (("team-nord", "Alles rund ums Team"), ("projekt-kranich", None)):
        channel = await _call(anna, "POST", channels, {"name": name, "topic": topic})
        seeded.channels[name] = str(channel["id"])

    team = seeded.channels["team-nord"]
    welcome = await _post(anna, team, "Willkommen im Kanal von **Team Nord**! 👋")
    clara_id = seeded.ids["clara"]
    await _post(
        ben,
        team,
        f"Danke! {mention('Clara Klein', clara_id)}, das Handbuch hat jetzt eine Urlaubsseite.",
        mentions=(clara_id,),
    )
    for client, emoji in ((clara, "👍"), (ben, "🎉")):
        await _call(client, "PUT", f"/api/messages/{welcome}/reactions/{emoji}")

    kranich, ben_id = seeded.channels["projekt-kranich"], seeded.ids["ben"]
    kickoff = await _post(
        anna,
        kranich,
        f"Kick-off am Montag um 10 Uhr. {mention('Ben Berg', ben_id)}, bringst du die Zahlen mit?",
        mentions=(ben_id,),
    )
    await _post(ben, kranich, "Mache ich, inklusive Prognose.", parent_id=kickoff)
    await _post(clara, kranich, "Ich lese mit und schreibe Protokoll.", parent_id=kickoff)


async def _dm(people: dict[str, httpx.AsyncClient], seeded: Seeded) -> None:
    dm = await _call(people["anna"], "POST", "/api/dms", {"user_ids": [seeded.ids["ben"]]})
    seeded.dm_id = str(dm["id"])
    await _post(people["anna"], seeded.dm_id, "Hast du kurz Zeit wegen des Budgets?")
    await _post(people["ben"], seeded.dm_id, "Klar, ruf einfach an.")


async def timeline_ready(
    client: httpx.AsyncClient, conversation_id: str, *, wait_seconds: float
) -> None:
    """Waits until the worker wrote the page's system entries (DemoFailed after
    `wait_seconds`; 0 checks once)."""
    deadline = time.monotonic() + wait_seconds
    path = f"/api/conversations/{conversation_id}/messages"
    while True:
        items = (await _call(client, "GET", path))["items"]
        if sum(1 for m in items if m["kind"] == "system") >= SYSTEM_ENTRIES:
            return
        if time.monotonic() >= deadline:
            raise DemoFailed("no system entries in the page discussion: is the worker running?")
        await asyncio.sleep(0.5)


async def _discussion(
    people: dict[str, httpx.AsyncClient], seeded: Seeded, wait_seconds: float
) -> None:
    ben, anna = people["ben"], people["anna"]
    thread = await _call(ben, "GET", f"/api/pages/{seeded.page_id}/thread")
    await timeline_ready(ben, str(thread["id"]), wait_seconds=wait_seconds)
    anna_id = seeded.ids["anna"]
    question = await _post(
        ben,
        str(thread["id"]),
        f"{mention('Anna Nord', anna_id)}, gilt die Regel auch für Teilzeit?",
        mentions=(anna_id,),
    )
    await _post(anna, str(thread["id"]), "Ja, anteilig nach Arbeitstagen.", parent_id=question)


async def seed(
    connect: Connect,
    *,
    admin_email: str,
    admin_password: str,
    people_password: str,
    settle: Callable[[], Awaitable[None]],
    wait_seconds: float = 60,
) -> Seeded:
    """Creates the demo. `connect()` gives a new client (own cookies, CSRF header) of
    the installation; `settle()` is awaited before the page discussion is used (a
    no-op against a running installation, whose worker writes the system entries)."""
    seeded = Seeded()
    admin = await _login(connect, admin_email, admin_password)
    await _people(admin, people_password, seeded)
    await _space(admin, seeded)
    people = {
        key: await _login(connect, email, people_password) for key, email in seeded.emails.items()
    }
    await _pages(people["anna"], seeded)
    await _channels(people, seeded)
    await _dm(people, seeded)
    await settle()
    await _discussion(people, seeded, wait_seconds)
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


async def _main(base: str, admin_email: str) -> int:
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
        seeded = await seed(
            connect,
            admin_email=admin_email,
            admin_password=admin_password,
            people_password=people_password,
            settle=nothing,
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
    print(f"demo ready: space Team Nord ({seeded.space_id}), people {people}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--base", default="http://127.0.0.1:8080")
    parser.add_argument("--admin", required=True, help="the admin's email")
    args = parser.parse_args(argv)
    return asyncio.run(_main(args.base.rstrip("/"), args.admin))


if __name__ == "__main__":
    sys.exit(main())

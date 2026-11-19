"""The data of the load test (plan M9, decision 20), through the public API only.

    LOAD_ADMIN_PASSWORD=… LOAD_PASSWORD=… python loadsetup.py BASE ADMIN_EMAIL STATE \
        [--people 200] [--teams 4] [--pages 250] [--tickets 250]

Creates PEOPLE people (system role member, password LOAD_PASSWORD), TEAMS team spaces
with PEOPLE/TEAMS editors each, per team PAGES published pages (one Markdown ZIP
import, about 2 KB of text each), one channel and TICKETS tickets assigned round-robin
to the team. Writes the ids (no password) as JSON to STATE for loadmix.py. The login
rate limits must be raised for the run (HERD_LOGIN_*_RATE_LIMIT_PER_MINUTE), as in
load.sh: the run logs PEOPLE people in within seconds.
"""

import argparse
import asyncio
import io
import json
import os
import random
import zipfile
from typing import Any

import httpx

HEADERS = {"X-Requested-With": "herd"}
WORDS = (
    "angebot ablauf antrag bericht budget dienst entwurf freigabe gruppe handbuch "
    "kunde lager leitung material meldung netz planung projekt quartal rechnung "
    "schicht server termin urlaub vertrag wartung zugang ziel schulung vorlage"
).split()


async def call(client: httpx.AsyncClient, method: str, path: str, body: Any = None) -> Any:
    response = await client.request(method, path, json=body, headers=HEADERS)
    # The admin writes faster than the write limit per person (HERD_WRITE_RATE_PER_MINUTE):
    # wait as long as the 429 says and send again.
    while response.status_code == 429 and "retry-after" in response.headers:
        await asyncio.sleep(min(int(response.headers["retry-after"]), 60))
        response = await client.request(method, path, json=body, headers=HEADERS)
    if response.status_code >= 300:
        raise SystemExit(f"{method} {path}: {response.status_code} {response.text[:200]}")
    return response.json() if response.content else None


def text(rng: random.Random, words: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(words))


def pages_zip(rng: random.Random, team: int, count: int) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for i in range(count):
            body = "\n\n".join(text(rng, 45) for _ in range(5))  # about 2 KB
            archive.writestr(f"seite-{team}-{i:04d}.md", f"# Seite {team}-{i}\n\n{body}\n")
    return buffer.getvalue()


async def _all(client: httpx.AsyncClient, path: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        sep = "&" if "?" in path else "?"
        url = f"{path}{sep}limit=100" + (f"&cursor={cursor}" if cursor else "")
        page = await call(client, "GET", url)
        items += page["items"]
        cursor = page.get("next_cursor")
        if not cursor:
            return items


async def _people(admin: httpx.AsyncClient, count: int, password: str) -> list[dict[str, str]]:
    gate = asyncio.Semaphore(4)  # each one is an argon2 hash on the server

    async def one(i: int) -> dict[str, str]:
        email = f"last{i:03d}@load.example"
        body = {"name": f"Last {i:03d}", "email": email, "password": password}
        async with gate:
            user = await call(admin, "POST", "/api/admin/users", body)
        return {"id": str(user["id"]), "email": email}

    return list(await asyncio.gather(*(one(i) for i in range(count))))


async def _team(
    admin: httpx.AsyncClient,
    rng: random.Random,
    team: int,
    people: list[dict[str, str]],
    pages: int,
    tickets: int,
) -> dict[str, Any]:
    space = await call(admin, "POST", "/api/spaces", {"name": f"Team {team}", "kind": "team"})
    space_id = str(space["id"])
    for person in people:
        member = {"member_type": "user", "member_id": person["id"], "role": "editor"}
        await call(admin, "PUT", f"/api/spaces/{space_id}/members", member)
    response = await admin.post(
        f"/api/spaces/{space_id}/import",
        content=pages_zip(rng, team, pages),
        headers={**HEADERS, "Content-Type": "application/zip"},
        timeout=300,
    )
    if response.status_code != 200:
        raise SystemExit(f"import: {response.status_code} {response.text[:200]}")
    page_ids = [str(p["id"]) for p in await _all(admin, f"/api/spaces/{space_id}/pages/tree")]
    channel = await call(
        admin, "POST", f"/api/spaces/{space_id}/channels", {"name": f"team-{team}", "topic": ""}
    )
    statuses = await _all(admin, f"/api/spaces/{space_id}/ticket-statuses")
    numbers: dict[str, list[int]] = {p["id"]: [] for p in people}
    for i in range(tickets):
        person = people[i % len(people)]
        body = {"title": text(rng, 6), "assignee": {"type": "user", "id": person["id"]}}
        ticket = await call(admin, "POST", f"/api/spaces/{space_id}/tickets", body)
        numbers[person["id"]].append(int(ticket["number"]))
    return {
        "space_id": space_id,
        "channel_id": str(channel["id"]),
        "page_ids": page_ids,
        "status_ids": [str(s["id"]) for s in statuses],
        "people": [{**p, "tickets": numbers[p["id"]]} for p in people],
    }


async def setup(args: argparse.Namespace) -> dict[str, Any]:
    rng = random.Random(20)  # noqa: S311 - load data, not secrets
    async with httpx.AsyncClient(base_url=args.base, timeout=60) as admin:
        login = {"email": args.admin, "password": os.environ["LOAD_ADMIN_PASSWORD"]}
        await call(admin, "POST", "/api/auth/login", login)
        people = await _people(admin, args.people, os.environ["LOAD_PASSWORD"])
        size = len(people) // args.teams
        teams = [
            await _team(admin, rng, t, people[t * size : (t + 1) * size], args.pages, args.tickets)
            for t in range(args.teams)
        ]
    print(f"{len(people)} people, {len(teams)} teams, state in {args.state}")
    return {"teams": teams}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base")
    parser.add_argument("admin")
    parser.add_argument("state")
    parser.add_argument("--people", type=int, default=200)
    parser.add_argument("--teams", type=int, default=4)
    parser.add_argument("--pages", type=int, default=250)
    parser.add_argument("--tickets", type=int, default=250)
    arguments = parser.parse_args()
    state = asyncio.run(setup(arguments))
    with open(arguments.state, "w", encoding="utf-8") as out:
        json.dump(state, out)

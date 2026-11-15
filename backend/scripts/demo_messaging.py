"""The demo's messages (M3), through the public API as the browser sends them: two
channels in Team Nord with messages, mentions, reactions and a thread, a direct message
between Anna and Ben, and the page discussion of „Urlaub", which starts once the
worker has written the page's system entries."""

import asyncio
import time
from typing import TYPE_CHECKING

import httpx

from scripts.demo_api import DemoFailed, call, mention, post

if TYPE_CHECKING:
    from scripts.demo_seed import Seeded

SYSTEM_ENTRIES = 3  # page.created, page.published, page.version_restored


async def channels(people: dict[str, httpx.AsyncClient], seeded: "Seeded") -> None:
    anna, ben, clara = people["anna"], people["ben"], people["clara"]
    channels = f"/api/spaces/{seeded.space_id}/channels"
    for name, topic in (("team-nord", "Alles rund ums Team"), ("projekt-kranich", None)):
        channel = await call(anna, "POST", channels, {"name": name, "topic": topic})
        seeded.channels[name] = str(channel["id"])

    team = seeded.channels["team-nord"]
    welcome = await post(anna, team, "Willkommen im Kanal von **Team Nord**! 👋")
    clara_id = seeded.ids["clara"]
    await post(
        ben,
        team,
        f"Danke! {mention('Clara Klein', clara_id)}, das Handbuch hat jetzt eine Urlaubsseite.",
        mentions=(clara_id,),
    )
    for client, emoji in ((clara, "👍"), (ben, "🎉")):
        await call(client, "PUT", f"/api/messages/{welcome}/reactions/{emoji}")

    kranich, ben_id = seeded.channels["projekt-kranich"], seeded.ids["ben"]
    kickoff = await post(
        anna,
        kranich,
        f"Kick-off am Montag um 10 Uhr. {mention('Ben Berg', ben_id)}, bringst du die Zahlen mit?",
        mentions=(ben_id,),
    )
    await post(ben, kranich, "Mache ich, inklusive Prognose.", parent_id=kickoff)
    await post(clara, kranich, "Ich lese mit und schreibe Protokoll.", parent_id=kickoff)


async def direct_message(people: dict[str, httpx.AsyncClient], seeded: "Seeded") -> None:
    dm = await call(people["anna"], "POST", "/api/dms", {"user_ids": [seeded.ids["ben"]]})
    seeded.dm_id = str(dm["id"])
    await post(people["anna"], seeded.dm_id, "Hast du kurz Zeit wegen des Budgets?")
    await post(people["ben"], seeded.dm_id, "Klar, ruf einfach an.")


async def timeline_ready(
    client: httpx.AsyncClient, conversation_id: str, *, wait_seconds: float
) -> None:
    """Waits until the worker wrote the page's system entries (DemoFailed after
    `wait_seconds`; 0 checks once)."""
    deadline = time.monotonic() + wait_seconds
    path = f"/api/conversations/{conversation_id}/messages"
    while True:
        items = (await call(client, "GET", path))["items"]
        if sum(1 for m in items if m["kind"] == "system") >= SYSTEM_ENTRIES:
            return
        if time.monotonic() >= deadline:
            raise DemoFailed("no system entries in the page discussion: is the worker running?")
        await asyncio.sleep(0.5)


async def discussion(
    people: dict[str, httpx.AsyncClient], seeded: "Seeded", wait_seconds: float
) -> None:
    ben, anna = people["ben"], people["anna"]
    thread = await call(ben, "GET", f"/api/pages/{seeded.page_id}/thread")
    await timeline_ready(ben, str(thread["id"]), wait_seconds=wait_seconds)
    anna_id = seeded.ids["anna"]
    question = await post(
        ben,
        str(thread["id"]),
        f"{mention('Anna Nord', anna_id)}, gilt die Regel auch für Teilzeit?",
        mentions=(anna_id,),
    )
    await post(anna, str(thread["id"]), "Ja, anteilig nach Arbeitstagen.", parent_id=question)

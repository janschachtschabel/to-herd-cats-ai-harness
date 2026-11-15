"""Changes of one automation racing each other under real commits (plan M7 decision
14, hard rule 6): two requests naming the same version, each over a connection of its
own; one wins, the other answers 409 `automation.version_conflict` (or 404 when the
winner deleted it)."""

import asyncio
import uuid
from typing import Any

from httpx import AsyncClient, Response

from tests.factories import login
from tests.factories_automations import runs_of
from tests.real_db import MakeRealClient, RealDb
from tests.support.openai_stub import OpenAIStub
from tests.test_automation_due_loop import _place

DAILY = {"kind": "recurring", "cron": "0 9 * * *", "time_zone": "Europe/Berlin"}


async def _made(real_db: RealDb, make_real_client: MakeRealClient, stub: OpenAIStub) -> Any:
    place = await _place(real_db, make_real_client, stub)
    clients: list[AsyncClient] = []
    for _ in range(2):
        client = await make_real_client()
        await login(client, real_db.owner_email)
        clients.append(client)
    body = {
        "agent_id": str(place["agent"]),
        "place": {"type": "dm"},
        "instruction": "Fasse zusammen.",
        "schedule": DAILY,
    }
    r = await clients[0].post("/api/automations", json=body)
    assert r.status_code == 201, r.text
    return clients, r.json()


def _one_wins(responses: tuple[Response, ...], *, gone: bool = False) -> None:
    ok = [r for r in responses if r.status_code < 300]
    lost = [r for r in responses if r.status_code >= 300]
    assert len(ok) == 1 and len(lost) == 1, [r.text for r in responses]
    allowed = {(409, "automation.version_conflict")}
    if gone:
        allowed.add((404, "automation.not_found"))
    assert (lost[0].status_code, lost[0].json()["error"]["code"]) in allowed


async def test_two_changes_with_one_version_one_wins(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    (a, b), made = await _made(real_db, make_real_client, openai_stub)
    path = f"/api/automations/{made['id']}"
    _one_wins(
        await asyncio.gather(
            a.patch(path, json={"version": 1, "instruction": "eins"}),
            b.patch(path, json={"version": 1, "instruction": "zwei"}),
        )
    )
    version = (await a.get(path)).json()["version"]
    assert version == 2
    _one_wins(
        await asyncio.gather(
            a.post(f"{path}/pause", json={"version": 2}),
            b.post(f"{path}/pause", json={"version": 2}),
        )
    )
    _one_wins(
        await asyncio.gather(
            a.post(f"{path}/resume", json={"version": 3}),
            b.post(f"{path}/resume", json={"version": 3}),
        )
    )
    _one_wins(
        await asyncio.gather(
            a.post(f"{path}/take-over", json={"version": 4}),
            b.post(f"{path}/take-over", json={"version": 4}),
        )
    )
    _one_wins(
        await asyncio.gather(a.delete(f"{path}?version=5"), b.delete(f"{path}?version=5")),
        gone=True,
    )
    assert (await a.get(path)).status_code == 404


async def test_run_now_twice_at_once_starts_one_run(
    real_db: RealDb, make_real_client: MakeRealClient, openai_stub: OpenAIStub
) -> None:
    (a, b), made = await _made(real_db, make_real_client, openai_stub)
    path = f"/api/automations/{made['id']}"
    responses = await asyncio.gather(a.post(f"{path}/run"), b.post(f"{path}/run"))
    assert [r.status_code for r in responses] == [200, 200], [r.text for r in responses]
    log = (await a.get(f"{path}/firings")).json()["items"]
    assert sorted(f["outcome"] for f in log) == ["skipped_busy", "started"]
    async with real_db.database.session_factory() as session:
        runs = await runs_of(session, uuid.UUID(made["id"]))
    assert [r.id for r in runs] == [uuid.UUID(next(f["run_id"] for f in log if f["run_id"]))]

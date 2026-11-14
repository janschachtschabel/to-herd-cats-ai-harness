"""Budgets under real commits and concurrent requests (`tests/real_db.py`): one
subject's budget created twice at once, one conflicts; two changes of one version, one
conflicts."""

import asyncio

from httpx import AsyncClient

from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

BUDGETS = "/api/ai/budgets"
ROUNDS = 4


async def _owners(real_db: RealDb, make_real_client: MakeRealClient) -> list[AsyncClient]:
    clients = [await make_real_client() for _ in range(2)]
    for client in clients:
        await login(client, real_db.owner_email)
    return clients


async def test_one_budget_per_subject_and_version(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    first, second = await _owners(real_db, make_real_client)
    me = (await first.get("/api/auth/me")).json()["user"]["id"]
    for round_ in range(ROUNDS):
        path = f"{BUDGETS}/organisation" if round_ % 2 else f"{BUDGETS}/users/{me}"
        created = await asyncio.gather(
            *(c.put(path, json={"tokens_per_day": 10, "version": None}) for c in (first, second))
        )
        assert sorted(r.status_code for r in created) == [200, 409], [r.text for r in created]
        made = next(r.json() for r in created if r.status_code == 200)
        changed = await asyncio.gather(
            *(
                c.put(path, json={"tokens_per_day": n, "version": made["version"]})
                for n, c in ((20, first), (30, second))
            )
        )
        assert sorted(r.status_code for r in changed) == [200, 409], [r.text for r in changed]
        version = next(r.json()["version"] for r in changed if r.status_code == 200)
        r = await first.delete(f"{BUDGETS}/{made['id']}", params={"version": version})
        assert r.status_code == 204, r.text

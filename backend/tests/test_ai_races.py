"""AI settings under real commits and concurrent requests: a connection deleted while
someone assigns it is either refused (409) or the assignment fails (422), never both
succeed; two writes of one version, one conflicts; a person's assignment created twice
at once, one conflicts."""

import asyncio
from typing import Any

from httpx import AsyncClient

from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

ROUNDS = 6


async def _owners(real_db: RealDb, make_real_client: MakeRealClient, n: int) -> list[AsyncClient]:
    clients = [await make_real_client() for _ in range(n)]
    for client in clients:
        await login(client, real_db.owner_email)
    return clients


async def _connection(client: AsyncClient, name: str) -> dict[str, Any]:
    body = {"name": name, "kind": "local", "base_url": "http://127.0.0.1:1/v1", "models": ["m"]}
    response = await client.post("/api/ai/connections", json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def test_deleting_and_assigning_a_connection_at_once(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    deleter, assigner = await _owners(real_db, make_real_client, 2)
    for round_ in range(ROUNDS):
        connection = await _connection(deleter, f"C{round_}")
        version = (await assigner.get("/api/ai/assignments")).json()["version"]
        target = {"connection_id": connection["id"], "model": "m"}
        deleted, assigned = await asyncio.gather(
            deleter.delete(f"/api/ai/connections/{connection['id']}", params={"version": 1}),
            assigner.put(
                "/api/ai/assignments/default", json={"target": target, "version": version}
            ),
        )
        outcome = (deleted.status_code, assigned.status_code)
        assert outcome in {(204, 422), (409, 200)}, (outcome, deleted.text, assigned.text)
        if assigned.status_code == 200:
            version = assigned.json()["version"]
            cleared = await assigner.put(
                "/api/ai/assignments/default", json={"target": None, "version": version}
            )
            assert cleared.status_code == 200


async def test_two_writes_of_one_version_one_conflicts(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    first, second = await _owners(real_db, make_real_client, 2)
    connection = await _connection(first, "C")
    target = {"connection_id": connection["id"], "model": "m"}
    answers = await asyncio.gather(
        first.put("/api/ai/assignments/default", json={"target": target, "version": 1}),
        second.put("/api/ai/assignments/groups", json={"items": [], "version": 1}),
    )
    assert sorted(a.status_code for a in answers) == [200, 409]
    me = (await first.get("/api/auth/me")).json()
    user_id = me["user"]["id"]
    created = await asyncio.gather(
        *(
            client.put(
                f"/api/ai/assignments/users/{user_id}", json={"no_ai": True, "version": None}
            )
            for client in (first, second)
        )
    )
    assert sorted(a.status_code for a in created) == [200, 409]

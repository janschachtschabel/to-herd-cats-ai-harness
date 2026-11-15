"""Concurrent requests over separate connections, with real commits (tests/real_db.py).

These hold the guarantees that rest on locks and constraints: one winner for the same
email or the same version, the rest get 409; the same space name never fails."""

import asyncio

from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

N = 8


async def test_same_email_creates_one_user(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    body = {"email": "twin@real.example.com", "name": "Twin", "password": "a-long-password"}
    responses = await asyncio.gather(*(owner.post("/api/admin/users", json=body) for _ in range(N)))
    assert sorted(r.status_code for r in responses) == [201] + [409] * (N - 1)


async def test_same_version_patch_has_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Race", "kind": "team"})).json()
    responses = await asyncio.gather(
        *(
            owner.patch(f"/api/spaces/{space['id']}", json={"name": f"N{i}", "version": 1})
            for i in range(N)
        )
    )
    assert sorted(r.status_code for r in responses) == [200] + [409] * (N - 1)


async def test_same_space_name_concurrently_creates_every_space(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    responses = await asyncio.gather(
        *(owner.post("/api/spaces", json={"name": "Twin", "kind": "team"}) for _ in range(N))
    )
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    assert len({r.json()["id"] for r in responses}) == N


async def test_a_new_session_is_usable_right_after_login(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    for _ in range(5):
        client = await make_real_client()
        await login(client, real_db.member_email)
        assert (await client.get("/api/spaces")).status_code == 200

"""Wiki writes that race, over separate connections with real commits (tests/real_db.py):
the tree lock decides slugs, paths and cycles on what the writers before committed."""

import asyncio
from typing import Any

from httpx import AsyncClient

from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

N = 8


async def _owner_with_space(
    make_real_client: MakeRealClient, real_db: RealDb
) -> tuple[AsyncClient, str]:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Race", "kind": "team"})).json()
    return owner, space["id"]


async def _create(owner: AsyncClient, space_id: str, title: str, **extra: Any) -> Any:
    return await owner.post(f"/api/spaces/{space_id}/pages", json={"title": title, **extra})


async def test_same_title_concurrently_gets_distinct_slugs(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _owner_with_space(make_real_client, real_db)
    responses = await asyncio.gather(*(_create(owner, space_id, "Zwilling") for _ in range(N)))
    assert all(r.status_code == 201 for r in responses), [r.text for r in responses]
    paths = sorted(r.json()["path"] for r in responses)
    assert paths == sorted(["zwilling"] + [f"zwilling-{i}" for i in range(2, N + 1)])
    assert sorted(r.json()["sort_order"] for r in responses) == list(range(N))


async def test_same_version_page_patch_has_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _owner_with_space(make_real_client, real_db)
    page = (await _create(owner, space_id, "Seite")).json()
    responses = await asyncio.gather(
        *(
            owner.patch(f"/api/pages/{page['id']}", json={"content_md": f"v{i}", "version": 1})
            for i in range(N)
        )
    )
    assert sorted(r.status_code for r in responses) == [200] + [409] * (N - 1)

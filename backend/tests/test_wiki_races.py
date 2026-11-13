"""Wiki writes that race, over separate connections with real commits (tests/real_db.py):
the tree lock decides slugs, paths and cycles on what the writers before committed."""

import asyncio
from typing import Any

from httpx import AsyncClient
from sqlalchemy import select

from app.modules.wiki.models import Page
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


async def _tree_is_consistent(real_db: RealDb, space_id: str) -> None:
    """Every page outside the trash hangs under a live parent of the same space, and
    its path is its parent's path plus its slug (so there is no cycle)."""
    async with real_db.database.session_factory() as s:
        rows = (await s.scalars(select(Page).where(Page.space_id == space_id))).all()
    by_id = {p.id: p for p in rows}
    for page in rows:
        if page.trashed_at is not None:
            continue
        if page.parent_id is None:
            assert page.path == page.slug, page.path
            continue
        parent = by_id[page.parent_id]
        assert parent.trashed_at is None, (page.path, "under a trashed parent")
        assert page.path == f"{parent.path}/{page.slug}", page.path


async def test_opposite_moves_never_make_a_cycle(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _owner_with_space(make_real_client, real_db)
    for round_ in range(5):
        a = (await _create(owner, space_id, f"A{round_}")).json()
        b = (await _create(owner, space_id, f"B{round_}")).json()
        responses = await asyncio.gather(
            owner.post(f"/api/pages/{a['id']}/move", json={"parent_id": b["id"], "version": 1}),
            owner.post(f"/api/pages/{b['id']}/move", json={"parent_id": a["id"], "version": 1}),
        )
        assert sorted(r.status_code for r in responses) == [200, 409], [r.text for r in responses]
        loser = next(r for r in responses if r.status_code == 409)
        assert loser.json()["error"]["code"] == "page.move_cycle"
    await _tree_is_consistent(real_db, space_id)


async def test_trash_racing_create_and_move_leaves_no_orphan(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, space_id = await _owner_with_space(make_real_client, real_db)
    for round_ in range(5):
        parent = (await _create(owner, space_id, f"Eltern{round_}")).json()
        other = (await _create(owner, space_id, f"Wandert{round_}")).json()
        responses = await asyncio.gather(
            owner.post(f"/api/pages/{parent['id']}/trash", json={"version": 1}),
            _create(owner, space_id, "Kind", parent_id=parent["id"]),
            owner.post(
                f"/api/pages/{other['id']}/move", json={"parent_id": parent["id"], "version": 1}
            ),
        )
        assert responses[0].status_code == 204, responses[0].text
        assert responses[1].status_code in (201, 422), responses[1].text
        assert responses[2].status_code in (200, 422), responses[2].text
    await _tree_is_consistent(real_db, space_id)

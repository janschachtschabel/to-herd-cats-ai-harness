"""Maintenance (plan M9 decision 9): while it is on, the API answers everything but
the probes, the metrics, `GET /api/maintenance` and the SPA with 503
`maintenance.active` and `Retry-After: 30`, from the process's cache (no database:
during a restore the tables are locked); the internal collab API tells the collab
process to close its connections (4503) and stores nothing."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.maintenance.cache import INACTIVE, MaintenanceCache, maintenance_cache
from app.modules.maintenance.models import MaintenanceReason
from app.modules.maintenance.state import MaintenanceState
from app.modules.wiki.collab_models import CollabInstance
from app.web.public import create_public_app
from tests.factories import login
from tests.factories_collab import check, grant_of, put_live
from tests.factories_wiki import Wiki, new_page, publish

SINCE = datetime(2026, 11, 16, 3, 0, tzinfo=UTC)
ON = MaintenanceState(active=True, reason=MaintenanceReason.RESTORE, started_at=SINCE)


@pytest.fixture
def maintenance() -> Iterator[MaintenanceCache]:
    cache = maintenance_cache()
    try:
        yield cache
    finally:
        cache.state = INACTIVE


def _is_maintenance(response) -> None:  # type: ignore[no-untyped-def]
    assert response.status_code == 503, response.text
    assert response.headers["retry-after"] == "30"
    error = response.json()["error"]
    assert error["code"] == "maintenance.active"
    assert len(error["trace_id"]) == 32


async def test_requests_during_maintenance_answer_503(
    maintenance: MaintenanceCache,
    make_client,  # type: ignore[no-untyped-def]
    owner_user,  # type: ignore[no-untyped-def]
    internal_client: AsyncClient,
) -> None:
    client: AsyncClient = await make_client(csrf=True)
    await login(client, owner_user.email)
    assert (await client.get("/api/maintenance")).json() == {
        "active": False,
        "reason": None,
        "started_at": None,
    }
    maintenance.state = ON
    _is_maintenance(await client.get("/api/auth/me"))
    _is_maintenance(await client.get("/api/spaces"))
    _is_maintenance(
        await client.post("/api/auth/login", json={"email": "x@example.com", "password": "y"})
    )
    _is_maintenance(await client.post("/mcp", json={}))
    _is_maintenance(await client.get("/api/openapi.json"))
    # Reachable: what the browser's maintenance page asks, the probes and the metrics.
    shown = await client.get("/api/maintenance")
    assert shown.status_code == 200
    assert shown.json() == {
        "active": True,
        "reason": "restore",
        "started_at": "2026-11-16T03:00:00Z",
    }
    for path in ("/health", "/ready", "/metrics"):
        assert (await internal_client.get(path)).status_code == 200, path
    maintenance.state = INACTIVE
    assert (await client.get("/api/auth/me")).status_code == 200


async def test_the_spa_is_served_in_maintenance(
    maintenance: MaintenanceCache, tmp_path: Path
) -> None:
    static = tmp_path / "dist"
    static.mkdir()
    (static / "index.html").write_text("<!doctype html><title>herd</title>")
    settings = get_settings().model_copy(update={"static_dir": static})
    app = create_public_app(settings)
    maintenance.state = ON
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in ("/", "/spaces/x", "/index.html"):
            page = await client.get(path)
            assert page.status_code == 200, path
            assert "herd" in page.text
        _is_maintenance(await client.get("/api/unknown"))


async def test_collab_closes_and_stores_nothing_in_maintenance(
    maintenance: MaintenanceCache,
    session: AsyncSession,
    collab: AsyncClient,
    wiki: Wiki,
) -> None:
    page = await publish(wiki.editor, await new_page(wiki.editor, wiki.space_id, "Live"))
    grant = await grant_of(session, wiki.editor, page)
    before = await check(collab, page, [grant])
    assert before.json()["maintenance"] is False
    maintenance.state = ON
    answer = await check(collab, page, [grant])
    assert answer.status_code == 200
    assert answer.json() == {
        "generation_ok": False,
        "generation": 0,
        "revoked_grants": [],
        "ended_grants": [],
        "maintenance": True,
    }
    body = {"grant": grant, "page_id": page["id"], "generation": 0}
    _is_maintenance(await collab.post("/internal/collab/auth", json=body))
    _is_maintenance(await put_live(collab, page, [grant]))
    load = await collab.get(
        f"/internal/collab/pages/{page['id']}",
        params={"generation": 0},
        headers={"X-Herd-Grant": grant},
    )
    _is_maintenance(load)


async def test_collab_instances_neither_announce_nor_release_in_maintenance(
    maintenance: MaintenanceCache, session: AsyncSession, collab: AsyncClient
) -> None:
    """A heartbeat writes too: during a replace it would wait on the swap's locks or
    land in the state being replaced. The collab process tolerates the 503 and
    announces itself again once maintenance ends (`collab/instance.mjs`)."""
    instance = uuid.uuid4()
    body = {"id": str(instance), "url": "ws://collab-a:1234", "draining": False}
    maintenance.state = ON
    _is_maintenance(await collab.post("/internal/collab/instances", json=body))
    _is_maintenance(await collab.delete(f"/internal/collab/instances/{instance}"))
    assert await session.get(CollabInstance, instance) is None
    maintenance.state = INACTIVE
    assert (await collab.post("/internal/collab/instances", json=body)).status_code == 204

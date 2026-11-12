from unittest.mock import AsyncMock

from alembic.script import ScriptDirectory
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.migrations import alembic_config, schema_is_compatible, stamp_head
from app.web.internal import create_internal_app, get_engine
from tests.conftest import json_lines


async def test_health_is_always_ok(internal_client):
    assert (await internal_client.get("/health")).json() == {"status": "ok"}


async def test_ready_is_ok_with_reachable_database_and_current_schema(internal_client):
    r = await internal_client.get("/ready")
    assert r.status_code == 200 and r.json() == {"status": "ready"}


async def test_ready_is_503_when_schema_behind(internal_client, monkeypatch):
    monkeypatch.setattr("app.web.internal.schema_is_compatible", AsyncMock(return_value=False))
    r = await internal_client.get("/ready")
    assert r.status_code == 503 and r.json()["reason"] == "migrations"


async def test_ready_is_503_when_database_unreachable():
    app = create_internal_app()
    dead = create_async_engine("postgresql+asyncpg://herd:herd@127.0.0.1:1/herd")
    app.dependency_overrides[get_engine] = lambda: dead
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://i") as c:
            r = await c.get("/ready")
    finally:
        await dead.dispose()
    assert r.status_code == 503
    assert r.json() == {"status": "not_ready", "reason": "database"}


async def test_schema_is_compatible_at_the_code_head(engine):
    # conftest stamps head after create_all.
    assert await schema_is_compatible(engine) is True


async def test_metrics_count_public_requests(client, internal_client):
    await client.get("/api/_test/ok")
    text = (await internal_client.get("/metrics")).text
    assert 'herd_http_requests_total{method="GET",route="/api/_test/ok",status="200"}' in text
    assert 'herd_http_request_duration_seconds_bucket{le="0.005",route="/api/_test/ok"}' in text


async def test_unmatched_paths_share_one_metrics_label(client, internal_client):
    await client.get("/api/_test/nowhere/abc123")
    text = (await internal_client.get("/metrics")).text
    assert "/api/_test/nowhere/abc123" not in text
    assert 'route="<unmatched>"' in text


async def test_probes_are_not_on_public_port_or_in_openapi(client):
    assert (await client.get("/health")).status_code == 404
    paths = (await client.get("/api/openapi.json")).json()["paths"]
    assert not any(p.startswith(("/health", "/ready", "/metrics", "/internal")) for p in paths)


async def test_internal_app_has_no_openapi(internal_client):
    assert (await internal_client.get("/openapi.json")).status_code == 404


def _baseline_revision() -> str:
    (base,) = ScriptDirectory.from_config(alembic_config()).get_bases()
    return base


async def _set_revision(engine, revision: str | None) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM alembic_version"))
        if revision is not None:
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:r)"), {"r": revision}
            )


async def _restore_head(engine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM alembic_version"))
        await conn.run_sync(stamp_head)


async def test_schema_is_not_compatible_without_a_recorded_revision(engine):
    await _set_revision(engine, None)
    try:
        assert await schema_is_compatible(engine) is False
    finally:
        await _restore_head(engine)


async def test_schema_is_not_compatible_at_a_known_older_revision(engine):
    # The new code's pods wait until the migration job has run.
    await _set_revision(engine, _baseline_revision())
    try:
        assert await schema_is_compatible(engine) is False
    finally:
        await _restore_head(engine)


async def test_schema_is_compatible_when_the_database_is_newer_than_the_code(engine):
    # A pre-upgrade migration ran a revision this (old) code does not know: the old pods
    # stay ready, because migrations are expand-first and backward compatible.
    await _set_revision(engine, "f00dfacecafe")
    try:
        assert await schema_is_compatible(engine) is True
    finally:
        await _restore_head(engine)


async def test_ready_stays_ok_while_the_database_is_newer(engine, internal_client):
    await _set_revision(engine, "f00dfacecafe")
    try:
        r = await internal_client.get("/ready")
    finally:
        await _restore_head(engine)
    assert r.status_code == 200 and r.json() == {"status": "ready"}


async def test_ready_is_503_at_a_known_older_revision(engine, internal_client):
    await _set_revision(engine, _baseline_revision())
    try:
        r = await internal_client.get("/ready")
    finally:
        await _restore_head(engine)
    assert r.status_code == 503 and r.json()["reason"] == "migrations"


async def test_ready_probe_does_not_log_on_success(internal_client, capsys):
    capsys.readouterr()
    assert (await internal_client.get("/ready")).status_code == 200
    lines = json_lines(capsys.readouterr().out)
    app_lines = [line for line in lines if line["logger"] != "httpx"]
    assert app_lines == []  # httpx is the test client; nothing from the app or alembic


async def test_unmatched_label_is_not_used_for_framework_routes(client, internal_client):
    await client.get("/api/openapi.json")
    text = (await internal_client.get("/metrics")).text
    assert 'route="/api/openapi.json"' in text


async def test_metrics_aggregate_the_multiprocess_directory_when_set(
    client, internal_client, monkeypatch, tmp_path
):
    await client.get("/api/_test/ok")
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", str(tmp_path))
    # An empty directory: no process has written values, so the in-process ones are not shown.
    assert "herd_http_requests_total{" not in (await internal_client.get("/metrics")).text

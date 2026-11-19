"""Backups in the administration (plan M9 task 13): only an owner (`backup.manage`)
sees them; everyone else gets 404 `backup.not_found` on every route, like an unknown
backup. Lists are paginated; "Jetzt sichern" writes a request a worker takes up."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.principal import SystemRole
from app.modules.audit.models import AuditLog
from app.modules.backups import service as backup_service
from app.modules.backups.models import BackupRun, BackupState, BackupTrigger
from app.modules.orgs.models import Organization
from tests.factories import MakeUser, login
from tests.support.clock import SettableClock

AT = datetime(2026, 11, 15, 2, 30, 7, tzinfo=UTC)
ARCHIVE = "herd-20261115T023007Z-1.0.0.tar"
ROUTES = [
    ("GET", "/api/backups", None),
    ("POST", "/api/backups", None),
    ("GET", "/api/backups/restore", None),
    ("GET", "/api/backups/archives", None),
    ("POST", "/api/backups/archives", b"x"),
    ("GET", f"/api/backups/archives/{ARCHIVE}", None),
    ("POST", f"/api/backups/archives/{ARCHIVE}/check", None),
    ("POST", f"/api/backups/archives/{ARCHIVE}/replace", {"confirm": "Test Org"}),
]


@pytest.fixture(autouse=True)
def backup_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "backups"
    path.mkdir(mode=0o700)
    monkeypatch.setattr(get_settings(), "backup_dir", path)
    monkeypatch.setattr(backup_service, "CLOCK", SettableClock(AT))
    return path


async def _client(make_client, user) -> AsyncClient:  # type: ignore[no-untyped-def]
    client: AsyncClient = await make_client(csrf=True)
    await login(client, user.email)
    return client


async def test_backup_routes_are_owner_only_and_paginated(  # type: ignore[no-untyped-def]
    session: AsyncSession, org: Organization, make_user: MakeUser, make_client, backup_dir: Path
) -> None:
    for hours in range(7):
        session.add(
            BackupRun(
                org_id=org.id,
                trigger=BackupTrigger.SCHEDULE,
                state=BackupState.OK,
                started_at=AT - timedelta(hours=hours),
                finished_at=AT - timedelta(hours=hours) + timedelta(minutes=1),
                archive=f"herd-20261115T0{hours}0000Z-1.0.0.tar",
                bytes=1000 + hours,
            )
        )
    for day in range(1, 6):
        (backup_dir / f"herd-2026111{day}T023007Z-1.0.0.tar").write_bytes(b"a" * day)
    (backup_dir / "notes.txt").write_text("not an archive")
    (backup_dir / "herd-20261116T023007Z-1.0.0.tar").symlink_to(backup_dir / "notes.txt")
    await session.flush()
    for role in (SystemRole.ADMIN, SystemRole.MEMBER, SystemRole.GUEST):
        client = await _client(make_client, await make_user(role))
        for method, path, body in ROUTES:
            kwargs = {"json": body} if isinstance(body, dict) else {"content": body}
            response = await client.request(method, path, **kwargs)
            assert response.status_code == 404, (role, method, path, response.text)
            assert response.json()["error"]["code"] == "backup.not_found"
    anonymous: AsyncClient = await make_client(csrf=True)
    assert (await anonymous.get("/api/backups")).status_code == 401

    owner = await _client(make_client, await make_user(SystemRole.OWNER))
    seen, cursor = [], None
    while True:
        params = {"limit": 3} | ({"cursor": cursor} if cursor else {})
        page = (await owner.get("/api/backups", params=params)).json()
        assert len(page["items"]) <= 3
        seen += [item["bytes"] for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert seen == [1000 + h for h in range(7)]  # newest first, each once
    assert (await owner.get("/api/backups", params={"limit": 101})).status_code == 422

    names, cursor = [], None
    while True:
        params = {"limit": 2} | ({"cursor": cursor} if cursor else {})
        page = (await owner.get("/api/backups/archives", params=params)).json()
        names += [(item["name"], item["bytes"], item["uploaded"]) for item in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert names == [(f"herd-2026111{d}T023007Z-1.0.0.tar", d, False) for d in range(5, 0, -1)]
    bad = await owner.get("/api/backups/archives", params={"cursor": "bm90LWEtbmFtZQ"})
    assert bad.status_code == 422


async def test_starting_a_backup_writes_a_request_for_the_worker(  # type: ignore[no-untyped-def]
    session: AsyncSession, make_user: MakeUser, make_client
) -> None:
    owner_user = await make_user(SystemRole.OWNER)
    owner = await _client(make_client, owner_user)
    started = await owner.post("/api/backups")
    assert started.status_code == 202, started.text
    body = started.json()
    assert (body["trigger"], body["state"], body["archive"]) == ("admin", "running", None)
    run = await session.get(BackupRun, body["id"])
    assert run is not None and run.started_at == AT
    again = await owner.post("/api/backups")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "backup.already_running")
    audit = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "backup.requested"))
    ).all()
    assert [(a.actor_id, a.target_id) for a in audit] == [(owner_user.id, run.id)]
    listed = (await owner.get("/api/backups")).json()["items"]
    assert [item["id"] for item in listed] == [body["id"]]

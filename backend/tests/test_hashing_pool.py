"""Password hashing holds no database connection and no lock (pool of one connection).

Logins, password changes and the people administration commit before they wait for a
hashing slot and re-read afterwards, so a login flood cannot take the pool: other
requests and the readiness probe are still served while hashing is queued.

The hashing in the first three tests cannot finish until the test opens its gate, so
what must not wait for it is shown served while it is held, with no bound on wall-clock
time (plan M9 task 8: a bound of 0.25 s failed on a loaded machine where nothing waited
for hashing; the single connection was only busy with the flood's own queries). A
request that waited for the held hashing would not be served within SERVED_WITHIN.
"""

import asyncio
import threading
from collections.abc import AsyncIterator, Awaitable
from weakref import WeakKeyDictionary

import pytest
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy import select, update

from app.core import security
from app.core.config import Settings, get_settings
from app.core.db import Database, set_database
from app.core.ratelimit import RateLimitHit
from app.core.security import hash_password
from app.modules.auth import service as auth_service
from app.modules.users import profile
from app.modules.users.models import User
from app.web.internal import create_internal_app, get_engine
from tests.factories import CSRF, PASSWORD, login
from tests.real_db import MakeRealClient, RealDb

SERVED_WITHIN = 15.0  # seconds; what waits for the held hashing is never served
HELD_AT_MOST = 30.0  # seconds a hashing waits for the gate, so a failed test ends


@pytest.fixture
async def one_connection(real_db: RealDb) -> AsyncIterator[Database]:
    database = Database(
        get_settings().test_database_url, pool_size=1, max_overflow=0, pool_timeout=10
    )
    set_database(database)
    try:
        yield database
    finally:
        set_database(real_db.database)
        await database.dispose()


class Gate:
    """Hashing waits here (in its thread) until the test opens the gate."""

    def __init__(self) -> None:
        self.open = threading.Event()
        self.entered = threading.Event()

    def pass_(self) -> None:
        self.entered.set()
        assert self.open.wait(HELD_AT_MOST), "the test never opened the gate"

    async def hashing(self) -> None:
        """Until a hashing has started and is held."""
        assert await asyncio.to_thread(self.entered.wait, SERVED_WITHIN)

    def close(self) -> None:
        self.open.clear()
        self.entered.clear()


def _held_hashing(monkeypatch: pytest.MonkeyPatch, *, queue: int = 16) -> Gate:
    settings = Settings(password_hash_concurrency=1, password_hash_queue=queue)
    monkeypatch.setattr(security, "get_settings", lambda: settings)
    monkeypatch.setattr(security, "_gates", WeakKeyDictionary())
    verify, hash_ = security.verify_password, security.hash_password
    gate = Gate()

    def held_verify(stored: str, password: str) -> bool:
        gate.pass_()
        return verify(stored, password)

    def held_hash(password: str) -> str:
        gate.pass_()
        return hash_(password)

    monkeypatch.setattr(security, "verify_password", held_verify)
    monkeypatch.setattr(security, "hash_password", held_hash)
    return gate


async def _served(request: Awaitable[Response]) -> Response:
    """The answer, which must come while the hashing is held."""
    return await asyncio.wait_for(request, SERVED_WITHIN)


async def _queue_full() -> None:
    """Until the hashing gate admits no one more (a slot and the queue taken)."""
    gate = security._gate()
    async with asyncio.timeout(SERVED_WITHIN):
        while True:
            if gate._inside >= gate._capacity:
                return
            await asyncio.sleep(0.01)


async def _wrong_login(client: AsyncClient, email: str) -> int:
    body = {"email": email, "password": "wrong-password"}
    return (await client.post("/api/auth/login", json=body, headers=CSRF)).status_code


async def test_a_login_flood_leaves_requests_and_probes_served(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    one_connection: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    gate = _held_hashing(monkeypatch)
    flood = [
        asyncio.create_task(
            _wrong_login(await make_real_client(client_ip=f"203.0.113.{i}"), real_db.member_email)
        )
        for i in range(4)
    ]
    try:
        await gate.hashing()  # one login hashes (held), the others wait for the slot
        me = await _served(owner.get("/api/auth/me"))
        assert me.status_code == 200
        internal = create_internal_app()
        internal.dependency_overrides[get_engine] = lambda: one_connection.engine
        transport = ASGITransport(app=internal)
        async with AsyncClient(transport=transport, base_url="http://internal") as probe:
            ready = await _served(probe.get("/ready"))
        assert ready.status_code == 200
    finally:
        gate.open.set()
        flooded = await asyncio.gather(*flood)  # never left running for the teardown
    assert flooded == [401] * 4


async def test_a_full_hashing_queue_answers_429_at_once(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    one_connection: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate = _held_hashing(monkeypatch, queue=1)
    clients = [await make_real_client(client_ip=f"198.51.100.{i}") for i in range(4)]
    first = [asyncio.create_task(_wrong_login(c, real_db.member_email)) for c in clients[:2]]
    try:
        await gate.hashing()  # one hashes (held)
        await _queue_full()  # one waits: the queue is full
        response = await _served(
            clients[2].post(
                "/api/auth/login",
                json={"email": real_db.member_email, "password": PASSWORD},
                headers=CSRF,
            )
        )
    finally:
        gate.open.set()
        firsts = await asyncio.gather(*first)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"
    assert response.json()["error"]["code"] == "server.busy"
    # Refused before any database work: not even the per-address counter was touched.
    async with real_db.database.session_factory() as s:
        hit = select(RateLimitHit.id).where(RateLimitHit.key == "login-ip:198.51.100.2")
        assert await s.scalar(hit) is None
    assert firsts == [401, 401]
    # A refused attempt does not count as a failure: the person logs in right after.
    later = {"email": real_db.member_email, "password": PASSWORD}
    assert (await clients[2].post("/api/auth/login", json=later, headers=CSRF)).status_code == 200


async def test_password_changes_and_administration_hold_no_connection_or_lock(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    one_connection: Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = await make_real_client()
    owner_me = await login(owner, real_db.owner_email)
    member = await make_real_client(client_ip="198.51.100.40")
    member_me = await login(member, real_db.member_email)
    gate = _held_hashing(monkeypatch)
    change = {"current_password": PASSWORD, "new_password": "a-new-password-1"}
    create = {"email": "new@real.example.com", "name": "Neu", "password": "a-new-password-2"}
    member_id, owner_id = member_me["user"]["id"], owner_me["user"]["id"]
    reset = {"password": "a-new-password-3", "version": member_me["user"]["version"]}
    slow_writes = [
        asyncio.create_task(member.post("/api/auth/me/password", json=change)),
        asyncio.create_task(owner.post("/api/admin/users", json=create)),
    ]
    try:
        await gate.hashing()  # one hashes (held), the other hashes next or waits
        # The people administration (the organisation's people lock) is still usable.
        rename = {"name": "Olga", "version": owner_me["user"]["version"]}
        renamed = await _served(owner.patch(f"/api/admin/users/{owner_id}", json=rename))
        assert renamed.status_code == 200
    finally:
        gate.open.set()
        changed, created = await asyncio.gather(*slow_writes)
    assert (changed.status_code, created.status_code) == (204, 201)
    # The member's version moved with the password change; an admin reset reads it fresh.
    people = (await owner.get("/api/admin/users")).json()["items"]
    reset["version"] = next(p["version"] for p in people if p["id"] == member_id)
    gate.close()
    resetting = asyncio.create_task(owner.patch(f"/api/admin/users/{member_id}", json=reset))
    try:
        await gate.hashing()  # the reset's new password is hashing (held)
        me = await _served(owner.get("/api/auth/me"))
        assert me.status_code == 200
    finally:
        gate.open.set()
        reset_done = await resetting
    assert reset_done.status_code == 200


async def _set_member(real_db: RealDb, **values: object) -> None:
    async with real_db.database.session_factory() as s:
        await s.execute(update(User).where(User.email == real_db.member_email).values(**values))
        await s.commit()


async def test_a_login_reads_the_person_again_after_hashing(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The password was changed while the old one was being checked: no session."""
    new_hash = hash_password("set-meanwhile-2")

    async def verify_while_someone_changes_it(stored: str, password: str) -> bool:
        await _set_member(real_db, password_hash=new_hash)
        return True

    monkeypatch.setattr(auth_service, "verify_password_async", verify_while_someone_changes_it)
    client = await make_real_client()
    body = {"email": real_db.member_email, "password": PASSWORD}
    response = await client.post("/api/auth/login", json=body, headers=CSRF)
    assert response.status_code == 401
    assert (await client.get("/api/auth/me")).status_code == 401


async def test_a_password_change_reads_the_person_again_after_hashing(
    real_db: RealDb, make_real_client: MakeRealClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another password set meanwhile (another tab, an admin): 409, nothing changed."""
    member = await make_real_client()
    await login(member, real_db.member_email)
    real_hash = profile.hash_password_async

    async def hash_while_someone_changes_it(password: str) -> str:
        await _set_member(real_db, password_hash=await real_hash("set-meanwhile-1"))
        return await real_hash(password)

    monkeypatch.setattr(profile, "hash_password_async", hash_while_someone_changes_it)
    change = {"current_password": PASSWORD, "new_password": "a-new-password-1"}
    response = await member.post("/api/auth/me/password", json=change)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "users.version_conflict"
    other = await make_real_client(client_ip="198.51.100.77")
    await login(other, real_db.member_email, "set-meanwhile-1")

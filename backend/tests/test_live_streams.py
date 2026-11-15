"""Live streams (plan M3 task 7): they end with the login session, are limited per
session, keep the connection alive and tell the client to reload after the LISTEN
connection was lost."""

import pytest
from sqlalchemy import update

from app.modules.users.models import User
from tests.live_helpers import LiveServer, drain, open_stream, until
from tests.live_people import Person, asyncio_wait, drain_events, person, say, team_channel
from tests.real_db import RealDb


async def test_stream_closes_after_logout(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, member = pair
    _, channel = await team_channel(owner, member)
    await drain(real_db.database)
    watcher, leaving = await owner.stream(real_db), await member.stream(real_db)
    assert (await member.client.post("/api/auth/logout")).status_code == 204
    await say(owner, channel)
    await drain(real_db.database)
    await watcher.until_event("message.created")  # the hub has handled the event
    await watcher.expect_nothing()
    await live.hub.check_sessions()  # what the hub does every 30 s
    await asyncio_wait(leaving)
    assert [e.name for e in drain_events(leaving)] == []  # nothing after the logout
    await watcher.close()
    await leaving.close()


async def test_the_session_check_runs_on_its_own(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.messaging import live as live_module

    monkeypatch.setattr(live_module, "SESSION_CHECK_SECONDS", 0.2)
    _, member = pair
    stream = await member.stream(real_db)
    async with real_db.database.session_factory() as session:  # deactivated, session kept
        await session.execute(update(User).where(User.id == member.id).values(is_active=False))
        await session.commit()
    await asyncio_wait(stream)
    await stream.close()


async def test_sixth_connection_is_429(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    _, member = pair
    streams = [
        await open_stream(member.client, real_db.database, member.org_id, member.id)
        for _ in range(5)
    ]
    sixth = await member.client.get("/api/stream")
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "live.too_many_streams"
    other_session = await person(live, real_db.member_email)  # another login: its own five
    extra = await open_stream(other_session.client, real_db.database, member.org_id, member.id)
    await streams[0].close()
    await until(lambda: live.hub.stream_count() == 5)
    again = await open_stream(member.client, real_db.database, member.org_id, member.id)
    for stream in [*streams[1:], extra, again]:
        await stream.close()


async def test_heartbeat_and_retry_hint(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.messaging import live_connection as live_module

    monkeypatch.setattr(live_module, "HEARTBEAT_SECONDS", 0.1)
    _, member = pair
    stream = await open_stream(member.client, real_db.database, member.org_id, member.id)
    await until(lambda: len(stream.comments) >= 2)
    assert stream.retry == [str(live_module.RETRY_MS)]
    await stream.close()


async def test_lost_listen_connection_sends_resync(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    _, member = pair
    stream = await member.stream(real_db)
    async with real_db.database.engine.connect() as connection:
        from sqlalchemy import text

        terminated = await connection.scalar(
            text(
                "SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity"
                " WHERE datname = current_database() AND query = 'LISTEN \"herd_live\"'"
            )
        )
    assert terminated == 1
    assert (await stream.next()).name == "resync"
    await until(lambda: live.hub.listening)
    await stream.settle()  # delivers again
    await stream.close()

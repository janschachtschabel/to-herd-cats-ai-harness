"""Usage (spec 7.4): one record per call through `record_usage`, cost only with a
price, admins read sums per day and key, a person reads their own."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.modules.ai.models import UsageRecord
from app.modules.ai.usage import record_usage
from app.modules.spaces.models import Space
from app.modules.users.models import User

CONNECTIONS = "/api/ai/connections"
USAGE = "/api/ai/usage"


async def connection(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    body = {
        "name": "Chat",
        "kind": "local",
        "base_url": "http://127.0.0.1:1/v1",
        "models": ["m1", "m2"],
        **fields,
    }
    response = await client.post(CONNECTIONS, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def record(
    session: AsyncSession, conn: dict[str, Any], user: User | None, **kw: Any
) -> UsageRecord:
    org_id = user.org_id if user else kw.pop("org_id")
    fields: dict[str, Any] = {"model": "m1", "tokens_in": 1000, "tokens_out": 500}
    fields.update({"duration_ms": 120, **kw})
    return await record_usage(
        session,
        org_id=org_id,
        connection_id=uuid.UUID(conn["id"]),
        user_id=user.id if user else None,
        **fields,
    )


async def test_cost_follows_the_price_and_stays_empty_without_one(
    owner: AsyncClient, session: AsyncSession, member: User
) -> None:
    prices = {"m1": {"input": "2.50", "output": "10"}}
    conn = await connection(owner, prices=prices)
    assert conn["prices"] == {"m1": {"input": "2.50", "output": "10"}}
    priced = await record(
        session, conn, member, tokens_in=2_000_000, tokens_out=100_000, tokens_cached=500_000
    )
    assert priced.cost == Decimal("6.00")  # 2 M × 2.50 + 0.1 M × 10; cached count as input
    unpriced = await record(session, conn, member, model="m2")
    assert unpriced.cost is None


async def test_counts_are_checked(session: AsyncSession, owner: AsyncClient, member: User) -> None:
    conn = await connection(owner)
    for bad in ({"tokens_in": -1}, {"tokens_cached": 2000}, {"duration_ms": -5}):
        with pytest.raises(ValueError):
            await record(session, conn, member, **bad)


async def test_prices_are_validated(owner: AsyncClient) -> None:
    for prices in (
        {"m1": {"input": "-1", "output": "1"}},
        {"m1": {"input": "1"}},
        {"m1": {"input": "x", "output": "1"}},
        {"": {"input": "1", "output": "1"}},
    ):
        response = await owner.post(CONNECTIONS, json={"name": "X", "prices": prices})
        assert response.status_code == 422, prices


async def _spread(
    session: AsyncSession, conn: dict[str, Any], people: list[User], space: Space
) -> None:
    """Two days: today a call of each person (one in the space), yesterday one more."""
    run = uuid7()
    for user in people:
        await record(session, conn, user, space_id=space.id, run_id=run)
    old = await record(session, conn, people[0], tokens_in=10, tokens_out=5)
    await session.execute(
        update(UsageRecord)
        .where(UsageRecord.id == old.id)
        .values(created_at=datetime.now(UTC) - timedelta(days=1))
    )
    await record(session, conn, None, org_id=people[0].org_id, tokens_in=7, tokens_out=0)  # a batch


async def test_admins_read_sums_per_day_and_key(
    owner: AsyncClient, session: AsyncSession, member: User, owner_user: User, team_space: Space
) -> None:
    conn = await connection(owner, prices={"m1": {"input": "1", "output": "1"}})
    await _spread(session, conn, [member, owner_user], team_space)
    by_day = (await owner.get(USAGE)).json()["items"]
    assert [(r["calls"], r["tokens_in"]) for r in by_day] == [(3, 2007), (1, 10)]
    assert by_day[0]["key_id"] is None and by_day[0]["name"] is None
    by_user = (await owner.get(USAGE, params={"by": "user"})).json()["items"]
    today = {r["name"]: r["calls"] for r in by_user if r["day"] == by_day[0]["day"]}
    assert today == {None: 1, member.name: 1, owner_user.name: 1}
    by_space = (await owner.get(USAGE, params={"by": "space"})).json()["items"]
    assert {r["name"] for r in by_space} == {team_space.name, None}
    by_connection = (await owner.get(USAGE, params={"by": "connection"})).json()["items"]
    assert {r["name"] for r in by_connection} == {"Chat"}
    assert Decimal(by_connection[0]["cost"]) == Decimal("0.003007")


async def test_usage_pages_and_periods(
    owner: AsyncClient, session: AsyncSession, member: User, owner_user: User, team_space: Space
) -> None:
    conn = await connection(owner)
    await _spread(session, conn, [member, owner_user], team_space)
    first = (await owner.get(USAGE, params={"by": "user", "limit": 2})).json()
    rest = (
        await owner.get(USAGE, params={"by": "user", "limit": 2, "cursor": first["next_cursor"]})
    ).json()
    assert len(first["items"]) == 2 and len(rest["items"]) == 2 and rest["next_cursor"] is None
    today = datetime.now(UTC).date()
    only_today = (await owner.get(USAGE, params={"from": today.isoformat()})).json()["items"]
    assert len(only_today) == 1 and only_today[0]["unpriced_calls"] == 3
    assert only_today[0]["cost"] is None
    for params in (
        {"from": today.isoformat(), "to": (today - timedelta(days=1)).isoformat()},
        {"from": (today - timedelta(days=400)).isoformat()},
    ):
        response = await owner.get(USAGE, params=params)
        assert response.json()["error"]["code"] == "ai.usage_period_invalid"


async def test_usage_of_one_run(owner: AsyncClient, session: AsyncSession, member: User) -> None:
    conn = await connection(owner)
    run = uuid7()
    await record(session, conn, member, run_id=run)
    await record(session, conn, member)
    rows = (await owner.get(USAGE, params={"run_id": str(run)})).json()["items"]
    assert [r["calls"] for r in rows] == [1]


async def test_a_person_reads_their_own_sums_with_ai_use(
    owner: AsyncClient,
    member_client: AsyncClient,
    session: AsyncSession,
    member: User,
    owner_user: User,
) -> None:
    conn = await connection(owner)
    await record(session, conn, member, tokens_in=40, tokens_out=2)
    await record(session, conn, owner_user, tokens_in=1000)
    hidden = await member_client.get(f"{USAGE}/me")
    assert hidden.status_code == 404 and hidden.json()["error"]["code"] == "ai.not_found"
    await owner.put(
        "/api/ai/assignments/default",
        json={"target": {"connection_id": conn["id"], "model": "m1"}, "version": 1},
    )
    mine = (await member_client.get(f"{USAGE}/me")).json()
    assert (mine["calls"], mine["tokens_in"], mine["tokens_out"]) == (1, 40, 2)
    assert "Chat" not in str(mine) and conn["id"] not in str(mine)
    assert (await member_client.get(USAGE)).status_code == 404

"""Plan M8 task 1: a bearer token resolves to the actor `/mcp` acts with. The person's
rights are read anew on every call (nothing is cached in the token), held to the
token's scope and mode. Unknown, revoked and expired tokens, and tokens of a person
who is inactive or lost `mcp.use`, all answer the same 401 on the same path: one
hash lookup, then one decision."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, can
from app.core.errors import Unauthorized
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.tokens.models import AccessToken, TokenMode
from app.modules.tokens.repository import TokenRepository
from app.modules.users.models import User
from tests.factories import MakeUser
from tests.factories_spaces import MakeSpace
from tests.factories_tokens import bearer, mcp_on, new_token, resolver
from tests.support.clock import SettableClock

INVALID = "token.invalid"


async def _row(session: AsyncSession, token_id: object) -> AccessToken:
    stmt = (
        select(AccessToken)
        .where(AccessToken.id == uuid.UUID(str(token_id)))
        .execution_options(populate_existing=True)
    )
    row = await session.scalar(stmt)
    assert row is not None
    return row


async def test_a_token_acts_as_its_person_held_to_its_scope(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> None:
    await mcp_on(owner)
    mine = await make_space(SpaceKind.TEAM, members=[(member, SpaceRole.EDITOR)])
    other = await make_space(SpaceKind.TEAM, members=[(member, SpaceRole.EDITOR)])
    token = await new_token(member_client, space_ids=[str(mine.id)], mode="write")
    found = await resolver(session).resolve(bearer(token))
    assert found.actor.principal == Principal.user(member.id)
    assert found.actor.org_id == member.org_id
    assert (found.token_id, found.name, found.mode) == (
        uuid.UUID(token["id"]),
        "Laptop",
        TokenMode.WRITE,
    )
    assert await can(session, found.actor, Action.PAGE_EDIT, mine.id)
    assert not await can(session, found.actor, Action.SPACE_READ, other.id)
    assert not found.actor.sees_drafts  # never drafts through a token


async def test_a_read_token_writes_nowhere(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> None:
    await mcp_on(owner)
    space = await make_space(SpaceKind.TEAM, members=[(member, SpaceRole.EDITOR)])
    token = await new_token(member_client, mode="read")
    found = await resolver(session).resolve(bearer(token))
    assert found.mode == TokenMode.READ
    assert await can(session, found.actor, Action.SPACE_READ, space.id)
    assert not await can(session, found.actor, Action.PAGE_EDIT, space.id)
    assert not await can(session, found.actor, Action.CHANNEL_POST, space.id)


async def test_a_space_taken_from_the_person_is_gone_at_once(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> None:
    await mcp_on(owner)
    space = await make_space(SpaceKind.TEAM, members=[(member, SpaceRole.VIEWER)])
    token = await new_token(member_client, space_ids=[str(space.id)])
    found = await resolver(session).resolve(bearer(token))
    assert await can(session, found.actor, Action.SPACE_READ, space.id)
    await SpaceRepository(session).remove_member(space.id, Principal.user(member.id))
    again = await resolver(session).resolve(bearer(token))
    assert not await can(session, again.actor, Action.SPACE_READ, space.id)


async def _refused(session: AsyncSession, header: str | None, clock: SettableClock) -> str:
    with pytest.raises(Unauthorized) as caught:
        await resolver(session, clock).resolve(header)
    return f"{caught.value.status_code} {caught.value.code} {caught.value.message}"


async def test_every_failure_answers_alike_after_one_lookup(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_user: MakeUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Structure, not wall-clock: every refusal takes the same path (one hash lookup,
    one decision) and gives the same 401."""
    await mcp_on(owner)
    lookups: list[bytes] = []
    original = TokenRepository.lookup

    async def counted(self: TokenRepository, digest: bytes) -> object:
        lookups.append(digest)
        return await original(self, digest)

    monkeypatch.setattr(TokenRepository, "lookup", counted)
    clock = SettableClock(datetime.now(UTC))
    expired = await new_token(member_client, name="alt", expires_in_days=1)
    revoked = await new_token(member_client, name="weg")
    r = await member_client.delete(f"/api/tokens/{revoked['id']}")
    assert r.status_code == 204, r.text
    later = SettableClock(clock.now() + timedelta(days=2))
    answers = {
        "missing": await _refused(session, None, clock),
        "not bearer": await _refused(session, "Basic eDp5", clock),
        "unknown": await _refused(session, "Bearer herd_pat_" + "A" * 43, clock),
        "revoked": await _refused(session, bearer(revoked), clock),
        "expired": await _refused(session, bearer(expired), later),
    }
    current = await new_token(member_client, name="jetzt")
    member.is_active = False
    await session.flush()
    answers["inactive"] = await _refused(session, bearer(current), clock)
    member.is_active = True
    member.system_role = SystemRole.GUEST
    await session.flush()
    answers["guest"] = await _refused(session, bearer(current), clock)
    member.system_role = SystemRole.MEMBER
    await session.flush()
    await mcp_on(owner, enabled=False)
    answers["switched off"] = await _refused(session, bearer(current), clock)
    assert set(answers.values()) == {f"401 {INVALID} {INVALID}"}
    assert len(lookups) == len(answers)  # one lookup each, even without a header


async def test_last_use_is_written_at_most_once_a_minute(
    session: AsyncSession, owner: AsyncClient, member_client: AsyncClient
) -> None:
    await mcp_on(owner)
    token = await new_token(member_client)
    assert token["last_used_at"] is None
    clock = SettableClock(datetime(2026, 11, 20, 10, 15, 42, 500_000, tzinfo=UTC))
    await resolver(session, clock).resolve(bearer(token))
    row = await _row(session, token["id"])
    assert row.last_used_at == datetime(2026, 11, 20, 10, 15, tzinfo=UTC)  # to the minute
    # Within the minute nothing is written: a value set behind its back stays.
    marker = datetime(2026, 11, 20, 10, 15, 0, 1, tzinfo=UTC)
    await session.execute(
        update(AccessToken).where(AccessToken.id == row.id).values(last_used_at=marker)
    )
    clock.advance(timedelta(seconds=10))
    await resolver(session, clock).resolve(bearer(token))
    assert (await _row(session, token["id"])).last_used_at == marker
    clock.advance(timedelta(minutes=1))
    await resolver(session, clock).resolve(bearer(token))
    assert (await _row(session, token["id"])).last_used_at == datetime(
        2026, 11, 20, 10, 16, tzinfo=UTC
    )
    listed = (await member_client.get("/api/tokens")).json()["items"]
    assert listed[0]["last_used_at"].startswith("2026-11-20T10:16:00")


async def test_a_token_of_another_organisation_sees_nothing_here(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> None:
    """The token's actor is in its person's organisation: a space of this one is not
    there for it, whatever its id."""
    await mcp_on(owner)
    elsewhere = Organization(name="Andere")
    session.add(elsewhere)
    await session.flush()
    foreign = await SpaceRepository(session).add(
        Space(org_id=elsewhere.id, kind=SpaceKind.OPEN, name="Fremd")
    )
    token = await new_token(member_client)
    found = await resolver(session).resolve(bearer(token))
    assert found.actor.org_id == member.org_id != elsewhere.id
    assert not await can(session, found.actor, Action.SPACE_READ, foreign.id)

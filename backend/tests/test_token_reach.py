"""Plan M8 task 1 (decision 4): what a token may read is the person's rights ∩ the
token's scope ∩ what the AI policy lets a connection at the organisation's MCP data
location receive (`tokens/reach.py`, built on `ai/policy_filters`); never drafts,
never pages locked for AI."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, can
from app.core.permissions import SpaceRole
from app.modules.ai.models import AiPolicy, DataLocation
from app.modules.spaces.models import Space, SpaceKind
from app.modules.tokens.reach import readable_page_ids, readable_spaces
from app.modules.users.models import User
from app.modules.wiki.models import Page
from tests.factories_spaces import MakeSpace, personal_space_of
from tests.factories_tokens import bearer, mcp_on, new_token, resolver
from tests.factories_wiki import new_page, publish


async def _spaces(make_space: MakeSpace, member: User, session: AsyncSession) -> dict[str, Space]:
    roles = [(member, SpaceRole.EDITOR)]
    made = {
        "any": await make_space(SpaceKind.TEAM, "Offen für KI", roles),
        "none": await make_space(SpaceKind.TEAM, "Ohne KI", roles),
        "eu": await make_space(SpaceKind.TEAM, "Nur EU", roles),
        "elsewhere": await make_space(SpaceKind.TEAM, "Nicht meins"),
        "open": await make_space(SpaceKind.OPEN, "Handbuch"),
    }
    made["none"].ai_policy = AiPolicy.NONE
    made["eu"].ai_policy = AiPolicy.RESTRICTED
    made["eu"].allowed_locations = [DataLocation.EU.value]
    await session.flush()
    return made


async def test_readable_spaces_are_rights_scope_and_policy_together(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> None:
    spaces = await _spaces(make_space, member, session)
    personal = await personal_space_of(session, member)
    await mcp_on(owner)  # external: the default
    everything = await new_token(member_client)
    found = await resolver(session).resolve(bearer(everything))
    assert found.location == DataLocation.EXTERNAL
    expected = {spaces["any"].id, spaces["open"].id, personal.id}
    assert set(await readable_spaces(session, found)) == expected
    # The policy holds in the actor itself, for code that does not ask `reach`.
    assert not await can(session, found.actor, Action.SPACE_READ, spaces["none"].id)
    assert not await can(session, found.actor, Action.SPACE_READ, spaces["eu"].id)
    # Clients in the house: the admin moves MCP to `eu`.
    await mcp_on(owner, data_location="eu")
    found = await resolver(session).resolve(bearer(everything))
    assert found.location == DataLocation.EU
    assert set(await readable_spaces(session, found)) == expected | {spaces["eu"].id}
    # A listed scope narrows it; a listed space the policy shuts stays shut.
    listed = await new_token(
        member_client, space_ids=[str(spaces["any"].id), str(spaces["none"].id)]
    )
    found = await resolver(session).resolve(bearer(listed))
    assert await readable_spaces(session, found) == [spaces["any"].id]


async def test_an_admins_token_leaves_other_peoples_personal_spaces_out(
    session: AsyncSession,
    owner: AsyncClient,
    owner_user: User,
    member: User,
) -> None:
    """ "All mine" is the person's spaces; an admin's power over someone else's
    personal space is not part of it."""
    await mcp_on(owner)
    token = await new_token(owner)
    found = await resolver(session).resolve(bearer(token))
    readable = await readable_spaces(session, found)
    assert (await personal_space_of(session, owner_user)).id in readable
    assert (await personal_space_of(session, member)).id not in readable


async def test_pages_are_published_and_open_to_ai_only(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    member: User,
    make_space: MakeSpace,
) -> None:
    spaces = await _spaces(make_space, member, session)
    space_id = spaces["any"].id
    published = await publish(member_client, await new_page(member_client, space_id, "Regeln"))
    draft = await new_page(member_client, space_id, "Entwurf")
    locked = await publish(member_client, await new_page(member_client, space_id, "Gesperrt"))
    r = await owner.put(  # locking for AI: a moderator's
        f"/api/pages/{locked['id']}/ai-lock", json={"no_ai": True, "version": locked["version"]}
    )
    assert r.status_code == 200, r.text
    shut = await publish(member_client, await new_page(member_client, spaces["none"].id, "Zu"))
    await mcp_on(owner)
    token = await new_token(member_client, mode="write")  # an editor, writing: still no drafts
    found = await resolver(session).resolve(bearer(token))
    ids = set(await session.scalars(select(Page.id).where(Page.id.in_(readable_page_ids(found)))))
    assert ids == {uuid.UUID(published["id"])}
    for hidden in (draft, locked, shut):
        assert uuid.UUID(hidden["id"]) not in ids

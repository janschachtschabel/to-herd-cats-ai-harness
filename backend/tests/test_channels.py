"""Channels (spec 5.3, 6.1): who sees, posts in and manages the channels of a space.

A channel is seen by whoever may read its space (`space.read`); `channel.post` comes
with `viewer`, `channel.manage` with `moderator`. A channel the caller cannot see
answers 404 `conversation.not_found`, never 403.
"""

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.outbox import EventOutbox
from app.core.pagination import PageParams
from app.core.principal import Principal, SystemRole
from app.modules.messaging.channels import ChannelService
from app.modules.messaging.service import ConversationService
from app.modules.orgs.models import Organization
from app.modules.spaces.models import Space, SpaceKind
from tests.factories import login
from tests.factories_spaces import personal_space_of
from tests.real_db import MakeRealClient, RealDb

CHANNELS = "/api/channels"


def channels_of(space: Space | str) -> str:
    space_id = space if isinstance(space, str) else space.id
    return f"/api/spaces/{space_id}/channels"


async def _create(client: AsyncClient, space: Space | str, name: str, **extra) -> dict:
    response = await client.post(channels_of(space), json={"name": name, **extra})
    assert response.status_code == 201, response.text
    return response.json()


async def test_moderator_creates_a_channel_and_viewers_see_it(
    owner: AsyncClient, member_client: AsyncClient, member, make_space, make_client
) -> None:
    space = await make_space(SpaceKind.TEAM, members=[(member, "viewer")])
    channel = await _create(owner, space, "  team-dienste ", topic="Absprachen")
    assert channel["kind"] == "channel" and channel["name"] == "team-dienste"
    assert channel["topic"] == "Absprachen" and channel["space_id"] == str(space.id)
    assert channel["archived_at"] is None and channel["version"] == 1
    assert channel["created_by"]["type"] == "user" and channel["can_post"] is True

    seen = await member_client.get(f"/api/conversations/{channel['id']}")
    assert seen.status_code == 200 and seen.json()["can_post"] is True
    listed = (await member_client.get(channels_of(space))).json()["items"]
    assert [c["id"] for c in listed] == [channel["id"]]


async def test_roles_below_moderator_cannot_manage(
    make_user, make_space, make_client, owner: AsyncClient
) -> None:
    for role, may_manage in (("viewer", False), ("editor", False), ("moderator", True)):
        user = await make_user()
        client = await make_client(csrf=True)
        await login(client, user.email)
        space = await make_space(SpaceKind.TEAM, members=[(user, role)])
        created = await client.post(channels_of(space), json={"name": "kanal"})
        assert created.status_code == (201 if may_manage else 403), (role, created.text)
        if not may_manage:
            assert created.json()["error"]["code"] == "auth.permission_denied"
            channel = await _create(owner, space, "kanal")
            patched = await client.patch(
                f"/api/conversations/{channel['id']}", json={"topic": "x", "version": 1}
            )
            assert patched.status_code == 403
            archived = await client.post(
                f"/api/conversations/{channel['id']}/archive", json={"version": 1}
            )
            assert archived.status_code == 403


async def test_members_post_in_open_spaces_but_moderate_nothing(
    owner: AsyncClient, member_client: AsyncClient, open_space: Space
) -> None:
    channel = await _create(owner, open_space, "handbuch")
    seen = (await member_client.get(f"/api/conversations/{channel['id']}")).json()
    assert seen["can_post"] is True
    refused = await member_client.post(channels_of(open_space), json={"name": "eigener"})
    assert refused.status_code == 403


async def test_invisible_channels_are_404(
    owner: AsyncClient, member_client: AsyncClient, team_space: Space
) -> None:
    channel = await _create(owner, team_space, "geheim")
    for method, path, body in (
        ("GET", f"/api/conversations/{channel['id']}", None),
        ("PATCH", f"/api/conversations/{channel['id']}", {"topic": "x", "version": 1}),
        ("POST", f"/api/conversations/{channel['id']}/archive", {"version": 1}),
        ("POST", f"/api/conversations/{channel['id']}/unarchive", {"version": 1}),
    ):
        response = await member_client.request(method, path, json=body)
        assert response.status_code == 404, (method, path)
        assert response.json()["error"]["code"] == "conversation.not_found"
    listed = await member_client.get(channels_of(team_space))
    assert listed.status_code == 404 and listed.json()["error"]["code"] == "space.not_found"
    assert (await member_client.get(CHANNELS)).json()["items"] == []


async def test_guests_see_only_spaces_they_belong_to(
    owner: AsyncClient,
    guest_client: AsyncClient,
    guest,
    open_space: Space,
    make_space,
) -> None:
    public = await _create(owner, open_space, "offen")
    assert (await guest_client.get(f"/api/conversations/{public['id']}")).status_code == 404
    assert (await guest_client.get(CHANNELS)).json()["items"] == []
    space = await make_space(SpaceKind.TEAM, members=[(guest, "viewer")])
    mine = await _create(owner, space, "projekt")
    listed = (await guest_client.get(CHANNELS)).json()["items"]
    assert [(c["id"], c["can_post"]) for c in listed] == [(mine["id"], True)]


async def test_other_organisations_never_see_a_channel(
    owner: AsyncClient, make_user, session: AsyncSession, team_space: Space
) -> None:
    channel = await _create(owner, team_space, "intern")
    other_org = Organization(name="Andere")
    session.add(other_org)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other_org)
    actor = Actor(other_org.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    with pytest.raises(NotFound) as hidden:
        await ConversationService(session).get(actor, uuid.UUID(channel["id"]))
    assert hidden.value.code == "conversation.not_found"
    assert (await ChannelService(session).list(actor, None, PageParams())).items == []
    with pytest.raises(NotFound):
        await ChannelService(session).list(actor, team_space.id, PageParams())


async def test_personal_spaces_have_no_channels(
    member_client: AsyncClient, member, session: AsyncSession
) -> None:
    space = await personal_space_of(session, member)
    response = await member_client.post(channels_of(space), json={"name": "notizen"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "channel.not_allowed"


async def test_names_are_unique_per_space_ignoring_case(
    owner: AsyncClient, team_space: Space, make_space
) -> None:
    first = await _create(owner, team_space, "Planung")
    clash = await owner.post(channels_of(team_space), json={"name": "planung"})
    assert clash.status_code == 409 and clash.json()["error"]["code"] == "channel.name_taken"
    other = await make_space(SpaceKind.TEAM)
    await _create(owner, other, "planung")  # another space: fine
    second = await _create(owner, team_space, "Termine")
    renamed = await owner.patch(
        f"/api/conversations/{second['id']}", json={"name": "PLANUNG", "version": 1}
    )
    assert renamed.status_code == 409 and renamed.json()["error"]["code"] == "channel.name_taken"
    same = await owner.patch(
        f"/api/conversations/{first['id']}", json={"name": "planung", "version": 1}
    )
    assert same.status_code == 200 and same.json()["name"] == "planung"


async def test_update_needs_the_current_version(owner: AsyncClient, team_space: Space) -> None:
    channel = await _create(owner, team_space, "alt")
    path = f"/api/conversations/{channel['id']}"
    updated = await owner.patch(path, json={"name": "neu", "topic": "Thema", "version": 1})
    assert updated.status_code == 200
    assert (updated.json()["name"], updated.json()["topic"], updated.json()["version"]) == (
        "neu",
        "Thema",
        2,
    )
    stale = await owner.patch(path, json={"topic": "anders", "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "conversation.version_conflict"
    assert stale.json()["error"]["details"] == {"current_version": 2}
    cleared = await owner.patch(path, json={"topic": None, "version": 2})
    assert cleared.json()["topic"] is None and cleared.json()["name"] == "neu"
    assert (await owner.patch(path, json={"name": None, "version": 3})).status_code == 422


async def test_archived_channels_stay_readable_but_take_no_posts(
    owner: AsyncClient, member_client: AsyncClient, member, make_space
) -> None:
    space = await make_space(SpaceKind.TEAM, members=[(member, "viewer")])
    channel = await _create(owner, space, "projekt-x")
    path = f"/api/conversations/{channel['id']}"
    archived = await owner.post(f"{path}/archive", json={"version": 1})
    assert archived.status_code == 200
    assert archived.json()["archived_at"] is not None and archived.json()["can_post"] is False
    again = await owner.post(f"{path}/archive", json={"version": 2})
    assert again.status_code == 409 and again.json()["error"]["code"] == "conversation.archived"
    seen = await member_client.get(path)
    assert seen.status_code == 200 and seen.json()["can_post"] is False
    assert (await member_client.get(channels_of(space))).json()["items"] == []
    with_archived = await member_client.get(channels_of(space), params={"include_archived": True})
    assert [c["id"] for c in with_archived.json()["items"]] == [channel["id"]]

    restored = await owner.post(f"{path}/unarchive", json={"version": 2})
    assert restored.status_code == 200 and restored.json()["archived_at"] is None
    assert restored.json()["can_post"] is True
    not_archived = await owner.post(f"{path}/unarchive", json={"version": 3})
    assert not_archived.status_code == 409
    assert not_archived.json()["error"]["code"] == "conversation.not_archived"


async def test_lists_are_by_name_and_paginated(
    owner: AsyncClient, team_space: Space, make_space
) -> None:
    other = await make_space(SpaceKind.TEAM)
    for space, name in ((team_space, "c-kanal"), (other, "A-kanal"), (team_space, "b-kanal")):
        await _create(owner, space, name)
    first = (await owner.get(CHANNELS, params={"limit": 2})).json()
    names = [c["name"] for c in first["items"]]
    rest = (await owner.get(CHANNELS, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    names += [c["name"] for c in rest["items"]]
    assert [n for n in names if n.endswith("-kanal")] == ["A-kanal", "b-kanal", "c-kanal"]
    assert rest["next_cursor"] is None
    in_space = (await owner.get(channels_of(team_space))).json()["items"]
    assert [c["name"] for c in in_space] == ["b-kanal", "c-kanal"]
    assert (await owner.get(CHANNELS, params={"limit": 101})).status_code == 422


async def test_names_and_topics_are_validated(owner: AsyncClient, team_space: Space) -> None:
    for bad in (
        {"name": ""},
        {"name": "   "},
        {"name": "x" * 81},
        {"name": "zwei\nzeilen"},
        {"name": "ok", "topic": "t" * 251},
        {},
    ):
        response = await owner.post(channels_of(team_space), json=bad)
        assert response.status_code == 422, bad


async def test_changes_are_events_in_the_same_transaction(
    owner: AsyncClient, team_space: Space, session: AsyncSession
) -> None:
    channel = await _create(owner, team_space, "ereignisse")
    path = f"/api/conversations/{channel['id']}"
    await owner.patch(path, json={"topic": "neu", "version": 1})
    await owner.post(f"{path}/archive", json={"version": 2})
    await owner.post(f"{path}/unarchive", json={"version": 3})
    events = (
        await session.scalars(
            select(EventOutbox)
            .where(EventOutbox.subject_id == channel["id"])
            .order_by(EventOutbox.id)
        )
    ).all()
    assert [e.type for e in events] == [
        "channel.created",
        "channel.updated",
        "channel.archived",
        "channel.unarchived",
    ]
    assert {e.subject_type for e in events} == {"conversation"}
    assert {e.space_id for e in events} == {team_space.id}
    assert all(e.payload == {"conversation_id": channel["id"]} for e in events)


async def test_same_name_concurrently_has_one_winner(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    space = (await owner.post("/api/spaces", json={"name": "Race", "kind": "team"})).json()
    responses = await asyncio.gather(
        *(
            owner.post(channels_of(space["id"]), json={"name": "Zwilling" if i % 2 else "zwilling"})
            for i in range(8)
        )
    )
    assert sorted(r.status_code for r in responses) == [201] + [409] * 7

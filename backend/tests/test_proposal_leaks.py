"""Proposals of spaces one may not read, and of pages one may not see, do not exist for
one (plan M6 task 5): not in the list, not by id, not to decide, not as an activity
entry. Each test names its mutation probe: the clause whose removal makes it fail
(each was removed once and the test seen failing; see the task report)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.groups.models import Group, GroupMember
from app.modules.messaging.notification_models import Notification
from app.modules.proposals.service import ProposalService
from app.modules.spaces.repository import SpaceRepository
from tests.factories_proposals import accept, agent_change, detail, listed, reject
from tests.factories_spaces import MakeSpace
from tests.factories_wiki import Wiki, new_page, publish
from tests.test_access import actor_of
from tests.test_proposal_events import _for_me, _handle


async def _secret_space_proposal(wiki: Wiki, session: AsyncSession, make_space: MakeSpace):  # type: ignore[no-untyped-def]
    """A team space only the wiki's moderator belongs to (as its moderator), with a
    page and an agent's proposal on it."""
    moderator = wiki.users["moderator"]
    secret = await make_space("team", "Geheim", members=[(moderator, SpaceRole.MODERATOR)])
    page = await new_page(wiki.moderator, secret.id, "Geheim", content_md="alt")
    actor = await actor_of(session, moderator)
    proposal = await ProposalService(session).propose_change(
        actor, uuid.UUID(page["id"]), "neu", "Grund", author=Principal.agent(uuid.uuid4())
    )
    return secret, page, proposal


async def test_a_space_one_cannot_read_hides_its_proposals(
    wiki: Wiki, session: AsyncSession, make_space: MakeSpace
) -> None:
    """Probe: with `space_ids` instead of `edit_space_ids` in the editor clause of
    `repository.visible` and without the list's space check, these people read,
    accept and reject the secret space's proposal."""
    secret, page, proposal = await _secret_space_proposal(wiki, session, make_space)
    for who in ("editor", "viewer", "outsider"):
        client = wiki.clients[who]
        r = await client.get(f"/api/spaces/{secret.id}/proposals")
        assert (r.status_code, r.json()["error"]["code"]) == (404, "space.not_found"), who
        for response in (
            await client.get(f"/api/proposals/{proposal.id}"),
            await accept(client, proposal),
            await reject(client, proposal),
        ):
            assert response.status_code == 404, (who, response.text)
            assert response.json()["error"]["code"] == "proposal.not_found"
    unknown = (await wiki.editor.get(f"/api/proposals/{uuid.uuid4()}")).json()["error"]
    hidden = (await wiki.editor.get(f"/api/proposals/{proposal.id}")).json()["error"]
    assert (unknown["code"], unknown["message"]) == (hidden["code"], hidden["message"])
    assert (await detail(wiki.moderator, proposal))["state"] == "open"
    assert (await listed(wiki.moderator, secret.id))["items"][0]["page_id"] == page["id"]


async def test_readers_without_page_edit_see_no_proposals(
    wiki: Wiki, session: AsyncSession
) -> None:
    """Probe: without `edit_space_ids` in `repository.visible`, the viewer sees the
    agent's proposal (and with it a draft's content and earlier versions)."""
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf", content_md="geheim")
    published = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Offen", content_md="alt")
    )
    on_draft = await agent_change(session, wiki, draft, "noch geheimer")
    on_published = await agent_change(session, wiki, published, "neu")
    assert (await listed(wiki.viewer, wiki.space_id))["items"] == []
    for proposal in (on_draft, on_published):
        r = await wiki.viewer.get(f"/api/proposals/{proposal.id}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "proposal.not_found"
    seen = {i["id"] for i in (await listed(wiki.editor2, wiki.space_id))["items"]}
    assert seen == {str(on_draft.id), str(on_published.id)}


async def test_an_author_without_page_edit_sees_only_published_pages(
    wiki: Wiki, session: AsyncSession
) -> None:
    """A person who cannot edit sees their own proposal while they may read the space
    and its page is published and outside the trash. Probes: without the page rule of
    the author clause, the viewer still reads their proposal on the trashed page;
    without `space_ids` in `repository.visible`, after leaving the space."""
    page = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Offen", content_md="alt")
    )
    viewer = await actor_of(session, wiki.users["viewer"])
    mine = await ProposalService(session).propose_change(
        viewer, uuid.UUID(page["id"]), "neu", "Bitte", author=viewer.principal
    )
    assert [i["id"] for i in (await listed(wiki.viewer, wiki.space_id))["items"]] == [str(mine.id)]
    trashed = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert trashed.status_code == 204
    assert (await listed(wiki.viewer, wiki.space_id))["items"] == []
    assert (await wiki.viewer.get(f"/api/proposals/{mine.id}")).status_code == 404
    other = await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, "Zwei", content_md="alt")
    )
    second = await ProposalService(session).propose_change(
        viewer, uuid.UUID(other["id"]), "neu", "Bitte", author=viewer.principal
    )
    assert (await wiki.viewer.get(f"/api/proposals/{second.id}")).status_code == 200
    viewer_principal = Principal.user(wiki.users["viewer"].id)
    await SpaceRepository(session).remove_member(wiki.space.id, viewer_principal)
    r = await wiki.viewer.get(f"/api/proposals/{second.id}")
    assert (r.status_code, r.json()["error"]["code"]) == (404, "proposal.not_found")


async def test_activity_entries_stay_in_the_space(
    wiki: Wiki, session: AsyncSession, make_space: MakeSpace
) -> None:
    """Probes: without the membership rule of `repository.moderators`, the system admin
    gets the secret space's entry; without `readers_of` in the handler, the moderator
    gets one for a page that went into the trash before the handler ran."""
    secret, _, _ = await _secret_space_proposal(wiki, session, make_space)
    group = Group(org_id=wiki.space.org_id, name="Moderierende")
    session.add(group)
    await session.flush()
    session.add(
        GroupMember(group_id=group.id, member_type="user", member_id=wiki.users["editor"].id)
    )
    await SpaceRepository(session).set_member(
        secret.id, Principal.group(group.id), SpaceRole.MODERATOR
    )
    await _handle(session)
    assert await _for_me(wiki.moderator) == [("proposal", await _page_of(session, secret.id))]
    assert len(await _for_me(wiki.editor)) == 1  # a moderator through a group
    for nobody in ("editor2", "viewer", "outsider", "admin"):
        assert await _for_me(wiki.clients[nobody]) == [], nobody
    # A moderator taken out before the handler runs gets nothing.
    await SpaceRepository(session).remove_member(secret.id, Principal.group(group.id))
    page = await new_page(wiki.moderator, secret.id, "Noch eins", content_md="alt")
    actor = await actor_of(session, wiki.users["moderator"])
    await ProposalService(session).propose_change(
        actor, uuid.UUID(page["id"]), "neu", "Grund", author=Principal.agent(uuid.uuid4())
    )
    await _handle(session)
    assert len(await _for_me(wiki.editor)) == 0  # its earlier entry went with the access
    count = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == wiki.users["editor"].id)
    )
    assert count == 1
    gone = await new_page(wiki.moderator, secret.id, "Weg", content_md="alt")
    await ProposalService(session).propose_change(
        actor, uuid.UUID(gone["id"]), "neu", "Grund", author=Principal.agent(uuid.uuid4())
    )
    before = len(await _for_me(wiki.moderator))
    trashed = await wiki.moderator.post(
        f"/api/pages/{gone['id']}/trash", json={"version": gone["version"]}
    )
    assert trashed.status_code == 204
    await _handle(session)
    rows = await session.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == wiki.users["moderator"].id)
    )
    assert rows == before  # nothing for the trashed page's proposal


async def _page_of(session: AsyncSession, space_id: object) -> str:
    from app.modules.wiki.models import Page  # noqa: PLC0415

    page_id = await session.scalar(
        select(Page.id).where(Page.space_id == space_id).order_by(Page.id).limit(1)
    )
    return str(page_id)

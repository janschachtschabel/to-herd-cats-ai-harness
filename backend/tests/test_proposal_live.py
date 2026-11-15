"""Proposals live (plan M6 task 5): every proposal event reaches, as `proposal.changed`
with the space's and the proposal's id only, every stream whose person may edit the
space's pages (who sees proposals), and nobody else: not a viewer of the space, not
an outsider, not another organisation; it stops the moment the person leaves the
space. A real server, the real worker handlers. Probe: with `space_action` always
`ticket.read`, the viewer's stream gets the event."""

import uuid

from sqlalchemy import select

from app.core.access import actor_for
from app.core.principal import Principal
from app.modules.auth.context import AuthContext
from app.modules.proposals.service import ProposalService
from app.modules.users.models import User
from tests.live_helpers import LiveServer, drain
from tests.live_people import Person, make_person, stranger
from tests.real_db import RealDb


async def _propose(real_db: RealDb, page_id: str) -> str:
    async with real_db.database.session_factory() as session:
        user = await session.scalar(select(User).where(User.email == real_db.owner_email))
        assert user is not None
        actor = await actor_for(session, AuthContext(user=user))
        proposal = await ProposalService(session).propose_change(
            actor, uuid.UUID(page_id), "geheim neu", "Grund", author=Principal.agent(uuid.uuid4())
        )
        await session.commit()
        return str(proposal.id)


async def _member(owner: Person, space: str, who: Person, role: str) -> None:
    added = await owner.client.put(
        f"/api/spaces/{space}/members",
        json={"member_type": "user", "member_id": who.id, "role": role},
    )
    assert added.status_code in (200, 201, 204), added.text


async def test_proposal_changes_reach_page_editors_only(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    owner, editor = pair
    viewer = await make_person(real_db, live, "viewer@real.example.com")
    outsider = await make_person(real_db, live, "outsider@real.example.com")
    other_org = await stranger(real_db, live)
    space = (await owner.client.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    await _member(owner, space["id"], editor, "editor")
    await _member(owner, space["id"], viewer, "viewer")
    page = await owner.client.post(
        f"/api/spaces/{space['id']}/pages", json={"title": "Geheim", "content_md": "geheim"}
    )
    assert page.status_code == 201, page.text
    await drain(real_db.database)
    streams = {
        name: await who.stream(real_db)
        for name, who in (
            ("editor", editor),
            ("viewer", viewer),
            ("outsider", outsider),
            ("other", other_org),
        )
    }
    proposal_id = await _propose(real_db, page.json()["id"])
    await drain(real_db.database)
    event = await streams["editor"].until_event("proposal.changed")
    assert event.data == {"space_id": space["id"], "proposal_id": proposal_id}
    for name in ("viewer", "outsider", "other"):
        await streams[name].expect_nothing()

    removed = await owner.client.delete(f"/api/spaces/{space['id']}/members/user/{editor.id}")
    assert removed.status_code == 204
    await drain(real_db.database)
    await streams["editor"].settle()
    rejected = await owner.client.post(f"/api/proposals/{proposal_id}/reject", json={"version": 1})
    assert rejected.status_code == 200, rejected.text
    await drain(real_db.database)
    for stream in streams.values():
        await stream.expect_nothing()
        await stream.close()


async def test_a_persons_proposal_reaches_its_author_even_as_a_viewer(
    real_db: RealDb, live: LiveServer, pair: tuple[Person, Person]
) -> None:
    """Plan M6 task 6 (ruling c): an author always hears of their proposal."""
    owner, _ = pair
    viewer = await make_person(real_db, live, "author@real.example.com")
    outsider = await make_person(real_db, live, "nobody@real.example.com")
    space = (await owner.client.post("/api/spaces", json={"name": "T", "kind": "team"})).json()
    await _member(owner, space["id"], viewer, "viewer")
    page = await owner.client.post(
        f"/api/spaces/{space['id']}/pages", json={"title": "Offen", "content_md": "alt"}
    )
    assert page.status_code == 201, page.text
    published = await owner.client.post(
        f"/api/pages/{page.json()['id']}/publish", json={"version": page.json()["version"]}
    )
    assert published.status_code == 200, published.text
    await drain(real_db.database)
    streams = {"viewer": await viewer.stream(real_db), "outsider": await outsider.stream(real_db)}
    async with real_db.database.session_factory() as session:
        user = await session.scalar(select(User).where(User.id == uuid.UUID(viewer.id)))
        assert user is not None
        actor = await actor_for(session, AuthContext(user=user))
        proposal = await ProposalService(session).propose_change(
            actor, uuid.UUID(page.json()["id"]), "neu", "Grund", author=Principal.user(user.id)
        )
        await session.commit()
    await drain(real_db.database)
    event = await streams["viewer"].until_event("proposal.changed")
    assert event.data == {"space_id": space["id"], "proposal_id": str(proposal.id)}
    await streams["outsider"].expect_nothing()
    for stream in streams.values():
        await stream.close()

"""Collab stage 2 (plan M9 task 15, decision 17): several collab instances announce
themselves; the relay sends every connection of a page to the one instance that owns
it (`collab_page_owner`), and an instance that no longer owns a page (its binding
expired and another took over with a higher `epoch`) can neither save nor check it:
409 `collab.not_owner`, the new owner's content stays."""

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.spaces.models import Space
from app.modules.wiki import collab_instances
from app.modules.wiki.collab_instances import INSTANCE_TTL, OWNER_TTL, CollabUnavailable
from app.modules.wiki.collab_models import CollabInstance, CollabPageOwner
from app.modules.wiki.models import Page
from tests.factories_collab import (
    announce,
    check,
    collab_auth,
    expect_error,
    get_page,
    grant_of,
    instance_id,
    load,
    put_live,
    route,
)
from tests.factories_wiki import Wiki, new_page
from tests.real_db import RealDb

X, Y, Z = instance_id(1), instance_id(2), instance_id(3)


async def _expire_binding(session: AsyncSession, page: dict[str, object]) -> None:
    await session.execute(
        update(CollabPageOwner)
        .where(CollabPageOwner.page_id == UUID(str(page["id"])))
        .values(expires_at=utcnow() - timedelta(seconds=1))
    )


async def _owner(session: AsyncSession, page: dict[str, object]) -> CollabPageOwner:
    found = await session.scalar(
        select(CollabPageOwner)
        .where(CollabPageOwner.page_id == UUID(str(page["id"])))
        .execution_options(populate_existing=True)
    )
    assert found is not None
    return found


async def test_all_connections_of_a_page_go_to_its_owner(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    for instance in (X, Y):
        assert (await announce(collab, instance)).status_code == 204
    first = await new_page(wiki.editor, wiki.space_id, "Eins")
    second = await new_page(wiki.editor, wiki.space_id, "Zwei")
    routes = [await route(session, first) for _ in range(3)]
    assert {(r.instance_id, r.url, r.epoch) for r in routes} == {(X, "ws://collab-1:1234", 1)}
    # The next page goes to the instance with fewer pages.
    other = await route(session, second)
    assert (other.instance_id, other.url, other.epoch) == (Y, "ws://collab-2:1234", 1)
    # The owner is admitted and learns its epoch; any other instance is not.
    grant = await grant_of(session, wiki.editor, first)
    r = await collab_auth(collab, grant, first, instance=X)
    assert r.status_code == 200 and r.json()["epoch"] == 1, r.text
    r = await load(collab, grant, first, instance=X)
    assert r.status_code == 200 and r.json()["epoch"] == 1, r.text
    expect_error(await collab_auth(collab, grant, first, instance=Y), 409, "collab.not_owner")
    expect_error(await load(collab, grant, first, instance=Y), 409, "collab.not_owner")


async def test_an_expired_owner_is_replaced_and_epoch_rises(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    await announce(collab, X)
    assert (await route(session, page)).epoch == 1
    await announce(collab, Y)
    # Still bound: the binding is good for OWNER_TTL from the last check.
    assert (await route(session, page)).instance_id == X
    assert (await _owner(session, page)).expires_at <= utcnow() + OWNER_TTL
    await _expire_binding(session, page)
    taken = await route(session, page)
    assert taken.epoch == 2
    # An owner whose instance stopped beating is replaced before its binding runs out.
    await session.execute(
        update(CollabInstance)
        .where(CollabInstance.id == taken.instance_id)
        .values(heartbeat_at=utcnow() - INSTANCE_TTL - timedelta(seconds=1))
    )
    again = await route(session, page)
    assert again.epoch == 3 and again.instance_id != taken.instance_id


async def test_a_stale_owner_cannot_save(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="Start")
    await announce(collab, X)
    old = await route(session, page)
    grant = await grant_of(session, wiki.editor, page)
    assert (await load(collab, grant, page, instance=X)).json()["epoch"] == old.epoch
    # X's binding runs out (its checks did not come through) and Y takes the page over.
    await _expire_binding(session, page)
    await announce(collab, Y, draining=False)
    await announce(collab, X, draining=True)
    new = await route(session, page)
    assert (new.instance_id, new.epoch) == (Y, old.epoch + 1)
    fresh = await grant_of(session, wiki.editor, page)
    assert (await load(collab, fresh, page, instance=Y)).json()["content_md"] == "Start"
    r = await put_live(collab, page, [fresh], content_md="Neu", instance=Y, epoch=new.epoch)
    assert r.status_code == 200, r.text
    # X still holds its document: its save and its check are refused, nothing is lost.
    r = await put_live(collab, page, [grant], content_md="Alt", instance=X, epoch=old.epoch)
    expect_error(r, 409, "collab.not_owner")
    expect_error(
        await check(collab, page, [grant], instance=X, epoch=old.epoch), 409, "collab.not_owner"
    )
    # The right instance with an old epoch is no owner either.
    r = await put_live(collab, page, [fresh], content_md="Alt", instance=Y, epoch=old.epoch)
    expect_error(r, 409, "collab.not_owner")
    assert (await get_page(wiki.editor, page))["content_md"] == "Neu"


async def test_a_draining_instance_gets_no_new_pages(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    pages = [await new_page(wiki.editor, wiki.space_id, f"Seite {n}") for n in range(4)]
    await announce(collab, X)
    assert (await route(session, pages[0])).instance_id == X
    await announce(collab, Y)
    await announce(collab, X, draining=True)
    # Once draining, always draining: a late heartbeat without the flag changes nothing.
    await announce(collab, X, draining=False)
    assert {(await route(session, page)).instance_id for page in pages[1:]} == {Y}
    # Its own page stays with it until it lets go (it saves first, then releases).
    assert (await route(session, pages[0])).instance_id == X
    await announce(collab, Y, draining=True)
    with pytest.raises(CollabUnavailable):
        await route(session, await new_page(wiki.editor, wiki.space_id, "Neu"))


async def test_a_released_instance_hands_its_pages_on(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    await announce(collab, X)
    await announce(collab, Z)
    await announce(collab, Y)
    assert (await route(session, page)).instance_id == X
    grant = await grant_of(session, wiki.editor, page)
    assert (await collab.delete(f"/internal/collab/instances/{X}")).status_code == 204
    assert await session.get(CollabInstance, X) is None
    taken = await route(session, page)
    assert taken.instance_id in {Y, Z} and taken.epoch == 2
    r = await put_live(collab, page, [grant], instance=X, epoch=1)
    expect_error(r, 409, "collab.not_owner")


async def test_without_a_live_instance_live_editing_is_unavailable(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    with pytest.raises(CollabUnavailable):
        await route(session, page)
    await announce(collab, X)
    await session.execute(
        update(CollabInstance).values(heartbeat_at=utcnow() - INSTANCE_TTL - timedelta(seconds=1))
    )
    with pytest.raises(CollabUnavailable) as refused:
        await route(session, page)
    assert (refused.value.status_code, refused.value.code) == (502, "collab.unavailable")


async def test_a_check_and_a_save_keep_the_binding_alive(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    await announce(collab, X)
    bound = await route(session, page)
    grant = await grant_of(session, wiki.editor, page)
    for call in (
        lambda: check(collab, page, [grant], instance=X, epoch=bound.epoch),
        lambda: put_live(collab, page, [grant], instance=X, epoch=bound.epoch),
        lambda: collab_auth(collab, grant, page, instance=X),
    ):
        await session.execute(
            update(CollabPageOwner).values(expires_at=utcnow() + timedelta(seconds=1))
        )
        r = await call()
        assert r.status_code == 200, r.text
        assert (await _owner(session, page)).expires_at > utcnow() + OWNER_TTL / 2
    # An expired binding no one took over still belongs to its owner (same epoch).
    await _expire_binding(session, page)
    assert (await check(collab, page, [grant], instance=X, epoch=bound.epoch)).status_code == 200
    assert (await route(session, page)).epoch == bound.epoch


async def test_a_collab_process_of_1_0_0_works_only_while_no_instance_owns_the_page(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    """During an upgrade from 1.0.0 an old collab process names no instance: it is
    served as before as long as no instance owns the page, so its last saves on
    SIGTERM are not lost; once an instance owns the page, it is a stale owner."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="Start")
    grant = await grant_of(session, wiki.editor, page)
    r = await collab_auth(collab, grant, page)
    assert r.status_code == 200 and r.json()["epoch"] is None
    assert (await load(collab, grant, page)).json()["epoch"] is None
    assert (await put_live(collab, page, [grant], content_md="Alt")).status_code == 200
    assert (await check(collab, page, [grant])).status_code == 200
    await announce(collab, X)
    await route(session, page)
    expect_error(await put_live(collab, page, [grant], content_md="Neu"), 409, "collab.not_owner")
    expect_error(await check(collab, page, [grant]), 409, "collab.not_owner")
    expect_error(await collab_auth(collab, grant, page), 409, "collab.not_owner")
    assert (await get_page(wiki.editor, page))["content_md"] == "Alt"


@pytest.mark.parametrize(
    "url",
    ["http://collab:1234", "ws://", "ws://collab:1234/path", "ws://a b:1", "ws://x" + "y" * 300],
)
async def test_an_instance_announces_a_websocket_address(collab: AsyncClient, url: str) -> None:
    expect_error(await announce(collab, X, url), 422, "validation_failed")


async def test_instance_routes_need_the_internal_token(
    internal: AsyncClient, internal_token: str
) -> None:
    body = {"id": str(X), "url": "ws://collab:1234", "draining": False}
    r = await internal.post("/internal/collab/instances", json=body)
    expect_error(r, 401, "internal.unauthorized")
    r = await internal.delete(f"/internal/collab/instances/{X}")
    expect_error(r, 401, "internal.unauthorized")


async def _real_page(session: AsyncSession, real_db: RealDb) -> Page:
    space = await session.scalar(select(Space).where(Space.org_id == real_db.org_id).limit(1))
    assert space is not None and space.owner_user_id is not None
    by = {"created_by_type": "user", "created_by_id": space.owner_user_id}
    page = Page(
        org_id=real_db.org_id,
        space_id=space.id,
        title="P",
        slug="p",
        path="p",
        updated_by_type="user",
        updated_by_id=space.owner_user_id,
        **by,
    )
    session.add(page)
    await session.flush()
    return page


async def test_two_relays_binding_one_page_at_once_agree(real_db: RealDb) -> None:
    """The claim is atomic: a second relay that tried to bind the page meanwhile waits
    for the first and takes its binding (one epoch, one owner)."""
    db = real_db.database
    async with db.session_factory() as session:
        for instance in (X, Y):
            await collab_instances.announce(
                session,
                instance_id=instance,
                url=f"ws://{instance.int}",
                draining=False,
                now=utcnow(),
            )
        page = await _real_page(session, real_db)
        await session.commit()
    async with db.session_factory() as first, db.session_factory() as second:
        won = await collab_instances.route(first, org_id=page.org_id, page_id=page.id, now=utcnow())
        # The second relay does not see the first's binding yet and tries to bind the
        # page itself: it waits on the row.
        other = asyncio.create_task(
            collab_instances.route(second, org_id=page.org_id, page_id=page.id, now=utcnow())
        )
        await asyncio.sleep(0.3)
        assert not other.done()
        await first.commit()
        taken = await asyncio.wait_for(other, timeout=5)
        await second.commit()
    assert (taken.instance_id, taken.epoch) == (won.instance_id, won.epoch) == (X, 1)

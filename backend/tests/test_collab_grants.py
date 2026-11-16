"""Collab grants (plan M9 task 6, decision 16, R14): the collab process acts only under
grants bound to one page and generation; a grant no one issued for them reaches no
page and ends no generation; grants expire unless a check extends them, are stored as
SHA-256 only and never show in an answer that is not for the collab process."""

import uuid
from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.auth.models import UserSession
from app.modules.wiki import collab_grants
from app.modules.wiki.collab_grants import GRANT_TTL, PREFIX, digest
from app.modules.wiki.collab_models import CollabGrant
from app.ops.restore_after import CLEARED_AFTER_RESTORE, finish_restore
from tests.factories_collab import (
    check,
    collab_auth,
    expect_error,
    get_page,
    grant_of,
    load,
    put_live,
    token_of,
)
from tests.factories_wiki import Wiki, new_page
from tests.support.clock import SettableClock


def _unknown() -> str:
    return PREFIX + "x" * 43


async def test_a_grant_works_only_for_its_page_and_generation(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    other = await new_page(wiki.editor, wiki.space_id, "Andere", content_md="b")
    grant = await grant_of(session, wiki.editor, page)
    assert grant.startswith(PREFIX) and len(grant) == len(PREFIX) + 43
    r = await collab_auth(collab, grant, page)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == str(wiki.users["editor"].id)
    assert (await load(collab, grant, page)).status_code == 200
    # Another page of the same space the same person may edit: nothing.
    for r in (
        await collab_auth(collab, grant, other),
        await load(collab, grant, other),
        await collab_auth(collab, grant, page, generation=1),
        await load(collab, grant, page, generation=1),
    ):
        error = expect_error(r, 401, "collab.grant_invalid")
        assert grant not in r.text and "details" not in error
    r = await put_live(collab, other, [grant], content_md="fremd")
    expect_error(r, 403, "collab.editors_revoked")
    assert grant not in r.text
    assert (await get_page(wiki.editor, other))["content_md"] == "b"
    r = await check(collab, other, [grant], unsaved=[grant])
    assert r.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_grants": [grant],
        "ended_grants": [],
    }
    # A Markdown save ends the generation: the grant of the old one opens nothing new.
    fresh = await get_page(wiki.editor, page)
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "neu", "version": fresh["version"]}
    )
    assert r.json()["collab_generation"] == 1
    expect_error(await load(collab, grant, page), 409, "collab.generation_ended")
    expect_error(await load(collab, grant, page, generation=1), 401, "collab.grant_invalid")
    # The session cookie itself is no grant.
    session_token = token_of(wiki.editor)
    expect_error(await collab_auth(collab, session_token, page), 401, "collab.grant_invalid")


async def test_an_unknown_grant_ends_no_generation(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    """A collab process that names grants no one issued for this page and generation
    (made up, of another page, of an older generation) as unsaved ends nothing."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    other = await new_page(wiki.editor, wiki.space_id, "Andere")
    foreign = await grant_of(session, wiki.editor, other)
    stale = await grant_of(session, wiki.editor, page)
    fresh = await get_page(wiki.editor, page)
    r = await wiki.editor.patch(
        f"/api/pages/{page['id']}", json={"content_md": "b", "version": fresh["version"]}
    )
    assert r.json()["collab_generation"] == 1
    mine = await grant_of(session, wiki.editor2, page, generation=1)
    strangers = [_unknown(), foreign, stale, "not-a-grant"]
    r = await check(collab, page, [mine], unsaved=strangers, generation=1)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "generation_ok": True,
        "generation": 1,
        "revoked_grants": sorted(strangers),
        "ended_grants": [],
    }
    # Without any grant of the page either.
    r = await check(collab, page, [], unsaved=strangers, generation=1)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (True, 1)
    assert (await get_page(wiki.editor, page))["collab_generation"] == 1
    # A grant issued for it whose person lost the right does end it.
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={"member_type": "user", "member_id": str(wiki.users["editor2"].id), "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    r = await check(collab, page, [mine], unsaved=[mine], generation=1)
    assert (r.json()["generation_ok"], r.json()["generation"]) == (False, 2)


async def test_a_grant_expires_after_ten_minutes_without_a_check(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    page_id = uuid.UUID(page["id"])
    org_id = wiki.users["editor"].org_id
    session_id = await session.scalar(
        select(UserSession.id).where(UserSession.user_id == wiki.users["editor"].id)
    )
    assert session_id is not None
    start = utcnow()
    grant = await collab_grants.mint(
        session, org_id=org_id, session_id=session_id, page_id=page_id, generation=0, now=start
    )

    async def resolved(at: timedelta) -> bool:
        ref = await collab_grants.resolve(
            session, grant, page_id=page_id, generation=0, now=start + at
        )
        return ref is not None

    assert await resolved(GRANT_TTL - timedelta(seconds=1))
    assert not await resolved(GRANT_TTL)
    # A check extends it by another ten minutes from then.
    found = await collab_grants.bound(session, [grant], page_id=page_id, generation=0)
    await collab_grants.renew(session, found.values(), now=start + timedelta(minutes=5))
    assert await resolved(timedelta(minutes=14))
    assert not await resolved(timedelta(minutes=15))
    # Over the API: a grant past its expiry opens nothing and is not extended by a check.
    api_grant = await grant_of(session, wiki.editor, page)
    await session.execute(
        update(CollabGrant)
        .where(CollabGrant.token_hash == digest(api_grant))
        .values(expires_at=utcnow() - timedelta(seconds=1))
    )
    expect_error(await collab_auth(collab, api_grant, page), 401, "collab.grant_invalid")
    r = await check(collab, page, [api_grant])
    assert r.json()["revoked_grants"] == [api_grant]
    expect_error(await load(collab, api_grant, page), 401, "collab.grant_invalid")
    # A live grant's check pushes its expiry.
    live = await grant_of(session, wiki.editor, page)
    before = await session.scalar(
        select(CollabGrant.expires_at).where(CollabGrant.token_hash == digest(live))
    )
    assert (await check(collab, page, [live])).json()["revoked_grants"] == []
    after = await session.scalar(
        select(CollabGrant.expires_at)
        .where(CollabGrant.token_hash == digest(live))
        .execution_options(populate_existing=True)
    )
    assert before is not None and after is not None and after >= before


async def test_logout_keeps_the_grant_for_saving_within_the_hour(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    """Review M2 R2 stays: a logout is no revocation. The grant opens nothing new, but
    what its person typed is saved under their name; once the ended session is cleared
    away, the grant is powerless, and its unsaved edits end the generation."""
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    anna = await grant_of(session, wiki.editor, page)
    ben = await grant_of(session, wiki.editor2, page)
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    expect_error(await collab_auth(collab, anna, page), 401, "collab.grant_invalid")
    r = await check(collab, page, [anna, ben], unsaved=[anna])
    assert r.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_grants": [],
        "ended_grants": [anna],
    }
    assert (await put_live(collab, page, [anna], content_md="Annas Satz")).status_code == 200
    versions = await wiki.editor2.get(f"/api/pages/{page['id']}/versions")
    assert versions.json()["items"][0]["author"]["id"] == str(wiki.users["editor"].id)
    # The ended session is cleared away (an hour later): the grant is powerless.
    session_id = await session.scalar(
        select(CollabGrant.session_id).where(CollabGrant.token_hash == digest(anna))
    )
    await session.execute(delete(UserSession).where(UserSession.id == session_id))
    row = await session.scalar(
        select(CollabGrant)
        .where(CollabGrant.token_hash == digest(anna))
        .execution_options(populate_existing=True)
    )
    assert row is not None and row.session_id is None
    expect_error(await put_live(collab, page, [anna, ben]), 403, "collab.editors_revoked")
    r = await check(collab, page, [ben], unsaved=[anna])
    assert r.json() == {
        "generation_ok": False,
        "generation": 1,
        "revoked_grants": [anna],
        "ended_grants": [],
    }


async def test_grants_are_stored_as_sha256_only(
    wiki: Wiki, session: AsyncSession, caplog: pytest.LogCaptureFixture
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    grant = await grant_of(session, wiki.editor, page)
    row = await session.scalar(select(CollabGrant).where(CollabGrant.token_hash == digest(grant)))
    assert row is not None and row.token_hash != grant
    stored = [str(getattr(row, c.key)) for c in inspect(CollabGrant).columns]
    assert not any(grant in value or grant[len(PREFIX) :] in value for value in stored)
    assert grant not in caplog.text


async def test_no_grant_is_left_after_a_restore(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    other = await new_page(wiki.editor, wiki.space_id, "Andere")
    for target in (page, page, other):
        await grant_of(session, wiki.editor, target)
    count = select(func.count()).select_from(CollabGrant)
    assert await session.scalar(count) == 3
    assert "collab_grant" in CLEARED_AFTER_RESTORE
    await finish_restore(
        session,
        archive_name="herd-test.tar",
        archive_created_at=utcnow(),
        revision_from="x",
        revision_to="x",
        clock=SettableClock(utcnow()),
    )
    assert await session.scalar(count) == 0


async def test_expired_grants_are_cleared_when_grants_are_issued(
    wiki: Wiki, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    old = await grant_of(session, wiki.editor, page)
    recent = await grant_of(session, wiki.editor, page)
    await session.execute(
        update(CollabGrant)
        .where(CollabGrant.token_hash == digest(old))
        .values(expires_at=utcnow() - timedelta(hours=1, seconds=1))
    )
    await session.execute(
        update(CollabGrant)
        .where(CollabGrant.token_hash == digest(recent))
        .values(expires_at=utcnow() - timedelta(minutes=59))
    )
    await grant_of(session, wiki.editor, page)
    hashes = set(await session.scalars(select(CollabGrant.token_hash)))
    assert digest(old) not in hashes and digest(recent) in hashes


async def test_collab_grant_has_only_read_columns(session: AsyncSession) -> None:
    expected = {"id", "org_id", "token_hash", "session_id", "page_id", "generation", "expires_at"}
    assert {c.name for c in CollabGrant.__table__.columns} == expected

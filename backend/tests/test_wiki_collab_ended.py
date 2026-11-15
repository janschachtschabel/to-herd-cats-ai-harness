"""A login session that merely ended is not a revocation (review M2 R2): after a logout
or an expiry the person's edits, made while they could edit, are saved under their
name, only their connection closes, and the generation goes on for everyone else.
A person who lost the right (role, deactivation, sessions ended by an administrator
or a password change) is revoked as before."""

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models_base import utcnow
from app.modules.auth.models import UserSession
from app.modules.wiki.collab_grants import digest
from app.modules.wiki.collab_models import CollabGrant
from tests.factories import login
from tests.factories_collab import check, expect_error, get_page, grant_of, put_live
from tests.factories_wiki import Wiki, new_page


async def _session_of(session: AsyncSession, grant: str) -> uuid.UUID:
    session_id = await session.scalar(
        select(CollabGrant.session_id).where(CollabGrant.token_hash == digest(grant))
    )
    assert session_id is not None
    return session_id


async def test_logout_with_unsaved_edits_is_saved_and_the_generation_goes_on(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="Start")
    anna = await grant_of(session, wiki.editor, page)
    ben = await grant_of(session, wiki.editor2, page)
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    r = await check(collab, page, [anna, ben], unsaved=[anna, ben])
    assert r.status_code == 200, r.text
    assert r.json() == {
        "generation_ok": True,
        "generation": 0,
        "revoked_grants": [],
        "ended_grants": [anna],
    }
    r = await put_live(collab, page, [anna, ben], content_md="Start\n\nAnnas Satz und Bens Text")
    assert r.status_code == 200, r.text
    after = await get_page(wiki.editor2, page)
    assert after["content_md"] == "Start\n\nAnnas Satz und Bens Text"
    assert after["collab_generation"] == 0
    versions = await wiki.editor2.get(f"/api/pages/{page['id']}/versions")
    assert versions.json()["items"][0]["author"]["id"] == str(wiki.users["editor"].id)


async def test_an_expired_session_has_ended(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    anna = await grant_of(session, wiki.editor, page)
    await session.execute(
        update(UserSession)
        .where(UserSession.id == await _session_of(session, anna))
        .values(expires_at=utcnow() - timedelta(seconds=1))
    )
    r = await check(collab, page, [anna], unsaved=[anna])
    assert r.json()["ended_grants"] == [anna]
    assert (r.json()["generation_ok"], r.json()["revoked_grants"]) == (True, [])
    assert (await put_live(collab, page, [anna], content_md="b")).status_code == 200


async def test_an_ended_session_without_the_right_is_revoked(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    anna = await grant_of(session, wiki.editor, page)
    ben = await grant_of(session, wiki.editor2, page)
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    r = await wiki.admin.put(
        f"/api/spaces/{wiki.space_id}/members",
        json={"member_type": "user", "member_id": str(wiki.users["editor"].id), "role": "viewer"},
    )
    assert r.status_code == 200, r.text
    r = await check(collab, page, [ben], unsaved=[anna])
    assert r.json() == {
        "generation_ok": False,
        "generation": 1,
        "revoked_grants": [anna],
        "ended_grants": [],
    }


async def test_sessions_ended_by_deactivation_are_revoked(
    wiki: Wiki, collab: AsyncClient, session: AsyncSession
) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Live", content_md="a")
    anna = await grant_of(session, wiki.editor, page)
    r = await wiki.admin.post(f"/api/admin/users/{wiki.users['editor'].id}/deactivate")
    assert r.status_code == 204, r.text
    r = await put_live(collab, page, [anna], content_md="b")
    expect_error(r, 403, "collab.editors_revoked")
    assert (await get_page(wiki.moderator, page))["content_md"] == "a"


async def test_logout_ends_the_session_and_a_login_keeps_fresh_ended_ones(
    wiki: Wiki, session: AsyncSession, collab: AsyncClient, make_client
) -> None:
    """A logout keeps the row (expired) so live editing can still tell whose session
    it was; logins clear only sessions ended more than an hour ago."""
    page = await new_page(wiki.editor, wiki.space_id, "Live")
    anna = await _session_of(session, await grant_of(session, wiki.editor, page))
    assert (await wiki.editor.post("/api/auth/logout")).status_code == 204
    assert (await wiki.editor.get("/api/auth/me")).status_code == 401
    row = await session.scalar(select(UserSession).where(UserSession.id == anna))
    assert row is not None and row.expires_at <= utcnow()
    await login(await make_client(csrf=True), wiki.users["moderator"].email)
    assert await session.scalar(select(UserSession.id).where(UserSession.id == anna))
    await session.execute(
        update(UserSession)
        .where(UserSession.id == anna)
        .values(expires_at=utcnow() - timedelta(hours=2))
    )
    await login(await make_client(csrf=True), wiki.users["moderator"].email)
    assert await session.scalar(select(UserSession.id).where(UserSession.id == anna)) is None

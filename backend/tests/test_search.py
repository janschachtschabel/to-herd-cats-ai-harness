"""Full-text search over pages (plan M2 task 5). Rights are filtered in the same
query: no hit, title, snippet or count from a space or a draft the actor cannot see."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.pagination import PageParams
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.orgs.models import Organization
from app.modules.search.service import SearchService
from app.modules.spaces.models import Space, SpaceKind
from app.modules.spaces.repository import SpaceRepository
from app.modules.users.models import User
from app.modules.wiki.service import PageService
from tests.factories import login
from tests.factories_wiki import Wiki, new_page, publish


async def _search(client: AsyncClient, q: str, **params: Any) -> Any:
    r = await client.get("/api/search", params={"q": q, **params})
    assert r.status_code == 200, r.text
    return r.json()


async def _ids(client: AsyncClient, q: str, **params: Any) -> list[str]:
    return [hit["id"] for hit in (await _search(client, q, **params))["items"]]


async def _published(wiki: Wiki, title: str, content: str = "", **kw: Any) -> dict[str, Any]:
    return await publish(
        wiki.editor, await new_page(wiki.editor, wiki.space_id, title, content_md=content, **kw)
    )


async def test_search_finds_german_inflection(wiki: Wiki) -> None:
    page = await _published(wiki, "Schichten", "Der Dienstplan für den Mai hängt aus.")
    assert await _ids(wiki.viewer, "Dienstpläne") == [page["id"]]
    assert await _ids(wiki.viewer, "dienstplan") == [page["id"]]


async def test_hit_carries_space_title_path_snippet_and_score(wiki: Wiki) -> None:
    parent = await _published(wiki, "Organisation")
    page = await _published(wiki, "Urlaub", "Urlaub beantragen.", parent_id=parent["id"])
    hit = (await _search(wiki.viewer, "beantragen"))["items"][0]
    assert {k: hit[k] for k in ("type", "id", "space_id", "space_name", "title", "path")} == {
        "type": "page",
        "id": page["id"],
        "space_id": wiki.space_id,
        "space_name": "Wiki",
        "title": "Urlaub",
        "path": "organisation/urlaub",
    }
    assert hit["score"] > 0 and "⟦beantragen⟧" in hit["snippet"]


async def test_title_hits_rank_before_content_hits(wiki: Wiki) -> None:
    body = await _published(wiki, "Allgemeines", "Hier steht etwas über Reisekosten.")
    title = await _published(wiki, "Reisekosten", "Formulare und Fristen.")
    assert await _ids(wiki.viewer, "Reisekosten") == [title["id"], body["id"]]


async def test_short_input_matches_title_prefix(wiki: Wiki) -> None:
    page = await _published(wiki, "Dienstreise", "Antrag stellen.")
    await _published(wiki, "Andere Seite", "Nichts über Dienst.")
    assert await _ids(wiki.viewer, "dienstr") == [page["id"]]
    # LIKE wildcards in the query are plain characters.
    assert await _ids(wiki.viewer, "%") == []
    assert await _ids(wiki.viewer, "_ienst") == []


async def test_search_never_returns_hits_from_invisible_space(
    wiki: Wiki, member_client: AsyncClient, guest_client: AsyncClient, make_space
) -> None:
    secret = await _published(wiki, "Geheimprojekt Zebra", "Zebra Zebra Zebra")
    open_space: Space = await make_space(SpaceKind.OPEN, "Handbuch")
    public = await publish(
        wiki.admin, await new_page(wiki.admin, open_space.id, "Zebrastreifen", content_md="Zebra")
    )
    assert set(await _ids(wiki.viewer, "Zebra")) == {secret["id"], public["id"]}
    for client in (member_client, wiki.outsider):
        result = await _search(client, "Zebra")
        assert [h["id"] for h in result["items"]] == [public["id"]]
        assert result["next_cursor"] is None
        assert "Geheim" not in str(result)
        # Prefix matching on the title reveals nothing either.
        assert await _ids(client, "Geheim") == []
    # A guest without a membership sees no space, not even the open one.
    assert (await _search(guest_client, "Zebra")) == {"items": [], "next_cursor": None}
    # Asking for the hidden space by id is the same 404 as for an unknown one.
    for space_id in (wiki.space_id, str(uuid7())):
        r = await member_client.get("/api/search", params={"q": "Zebra", "space_id": space_id})
        assert r.status_code == 404 and r.json()["error"]["code"] == "space.not_found"


async def test_drafts_only_for_editors_of_that_space(wiki: Wiki) -> None:
    draft = await new_page(wiki.editor, wiki.space_id, "Entwurf Kolibri", content_md="Kolibri")
    done = await _published(wiki, "Fertig", "Kolibri im Text")
    assert set(await _ids(wiki.editor2, "Kolibri")) == {draft["id"], done["id"]}
    assert set(await _ids(wiki.admin, "Kolibri")) == {draft["id"], done["id"]}
    viewer = await _search(wiki.viewer, "Kolibri")
    assert [h["id"] for h in viewer["items"]] == [done["id"]]
    assert "Entwurf" not in str(viewer)
    assert await _ids(wiki.viewer, "Entw") == []


async def test_drafts_of_other_spaces_stay_hidden_from_their_editors(
    wiki: Wiki, make_space
) -> None:
    other: Space = await make_space(
        SpaceKind.TEAM, "Anders", members=[(wiki.users["editor"], "viewer")]
    )
    await new_page(wiki.admin, other.id, "Fremder Entwurf", content_md="Pinguin")
    own = await new_page(wiki.editor, wiki.space_id, "Eigener Entwurf", content_md="Pinguin")
    assert await _ids(wiki.editor, "Pinguin") == [own["id"]]


async def test_trashed_pages_are_not_found(wiki: Wiki) -> None:
    page = await _published(wiki, "Altlast", "Flamingo")
    r = await wiki.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": page["version"]}
    )
    assert r.status_code == 204
    assert await _ids(wiki.moderator, "Flamingo") == []


async def test_other_organisations_are_never_searched(
    wiki: Wiki, session: AsyncSession, make_user
) -> None:
    elsewhere = Organization(name="Elsewhere")
    session.add(elsewhere)
    await session.flush()
    stranger: User = await make_user("owner", organization=elsewhere)
    space = Space(org_id=elsewhere.id, kind=SpaceKind.OPEN, name="Fremd")
    session.add(space)
    await session.flush()
    actor = Actor(elsewhere.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    pages = PageService(session)
    foreign = await pages.create(actor, space.id, None, "Okapi", "Okapi")
    await pages.publish(actor, foreign.id, foreign.version)
    mine = await _published(wiki, "Okapi hier", "Okapi")
    assert await _ids(wiki.admin, "Okapi") == [mine["id"]]
    found = await SearchService(session).search(actor, "Okapi", params=PageParams())
    assert [h.id for h in found.items] == [foreign.id]


async def test_snippet_has_markers_and_no_html(wiki: Wiki) -> None:
    await _published(
        wiki, "Markup", "Vorher <b>fett</b> <script>alert(1)</script> der Leguan nachher."
    )
    snippet = (await _search(wiki.viewer, "Leguan"))["items"][0]["snippet"]
    assert "⟦Leguan⟧" in snippet
    assert "<b>" not in snippet and "<script>" not in snippet


async def test_filter_by_space_and_tags(wiki: Wiki, make_space) -> None:
    other: Space = await make_space(
        SpaceKind.TEAM, "Anders", members=[(wiki.users["editor"], "editor")]
    )
    here = await _published(wiki, "Gecko hier", "Gecko")
    there = await new_page(wiki.editor, other.id, "Gecko dort", content_md="Gecko")
    assert set(await _ids(wiki.editor, "Gecko")) == {here["id"], there["id"]}
    assert await _ids(wiki.editor, "Gecko", space_id=wiki.space_id) == [here["id"]]
    a = (await wiki.admin.post("/api/tags", json={"name": "A"})).json()
    b = (await wiki.admin.post("/api/tags", json={"name": "B"})).json()
    for page, tags in ((here, [a["id"], b["id"]]), (there, [a["id"]])):
        fresh = (await wiki.editor.get(f"/api/pages/{page['id']}")).json()
        r = await wiki.editor.put(
            f"/api/pages/{page['id']}/tags", json={"tag_ids": tags, "version": fresh["version"]}
        )
        assert r.status_code == 200, r.text
    assert set(await _ids(wiki.editor, "Gecko", tag=a["id"])) == {here["id"], there["id"]}
    # Several tags: pages carrying all of them.
    assert await _ids(wiki.editor, "Gecko", tag=[a["id"], b["id"]]) == [here["id"]]


async def test_results_are_paginated(wiki: Wiki) -> None:
    ids = {(await _published(wiki, f"Seite {i}", "Tapir " * (i + 1)))["id"] for i in range(5)}
    first = await _search(wiki.viewer, "Tapir", limit=2)
    seen = [h["id"] for h in first["items"]]
    cursor = first["next_cursor"]
    while cursor:
        page = await _search(wiki.viewer, "Tapir", limit=2, cursor=cursor)
        seen += [h["id"] for h in page["items"]]
        cursor = page["next_cursor"]
    assert len(seen) == 5 and set(seen) == ids
    scores = [h["score"] for h in first["items"]]
    assert scores == sorted(scores, reverse=True)


async def test_empty_query_is_an_empty_list(wiki: Wiki) -> None:
    await _published(wiki, "Etwas", "Inhalt")
    for q in ("", "   ", "\t"):
        assert await _search(wiki.viewer, q) == {"items": [], "next_cursor": None}
    r = await wiki.viewer.get("/api/search")
    assert r.status_code == 200 and r.json()["items"] == []


async def test_weird_queries_do_not_error(wiki: Wiki) -> None:
    await _published(wiki, "Etwas", "Inhalt mit a:* und Zeichen")
    for q in ['"', "a:*", "'' OR", "x" * 500, "!!!", "&|!()<->", "\\", "-", "or or or"]:
        r = await wiki.viewer.get("/api/search", params={"q": q})
        assert r.status_code == 200, (q, r.text)


async def test_guest_with_a_membership_sees_only_that_space_published(
    wiki: Wiki, make_space, make_user, make_client, session: AsyncSession
) -> None:
    guest: User = await make_user(SystemRole.GUEST)
    await SpaceRepository(session).set_member(
        wiki.space.id, Principal.user(guest.id), SpaceRole.VIEWER
    )
    client = await make_client(csrf=True)
    await login(client, guest.email)
    open_space: Space = await make_space(SpaceKind.OPEN, "Handbuch")
    await publish(
        wiki.admin, await new_page(wiki.admin, open_space.id, "Luchs offen", content_md="Luchs")
    )
    done = await _published(wiki, "Luchs fertig", "Luchs")
    await new_page(wiki.editor, wiki.space_id, "Luchs Entwurf", content_md="Luchs")
    assert await _ids(client, "Luchs") == [done["id"]]

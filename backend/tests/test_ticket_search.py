"""Tickets in the search (plan M4 task 4, spec 11): full text over title and
description, rights in the same statement (spaces where the caller may read tickets),
one ranking and cursor with pages and messages; input shaped like a key (`HC-42`,
`42`) puts that ticket first, if the caller may see it."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.modules.spaces.repository import SpaceRepository
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket
from tests.factories_wiki import new_page, publish


async def _hits(client: AsyncClient, q: str, **params: Any) -> list[dict[str, Any]]:
    r = await client.get("/api/search", params={"q": q, **params})
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


async def _ids(client: AsyncClient, q: str, **params: Any) -> list[str]:
    return [hit["id"] for hit in await _hits(client, q, **params)]


async def test_a_ticket_hit_carries_key_title_status_space_and_snippet(desk: Desk) -> None:
    ticket = await new_ticket(
        desk.editor,
        desk.space_id,
        "Drucker reparieren",
        kind="bug",
        description_md="Der Drucker im Flur druckt nur noch Streifen.",
    )
    (hit,) = await _hits(desk.viewer, "Streifen")
    assert {k: hit[k] for k in ("type", "id", "number", "key", "title", "kind", "space_id")} == {
        "type": "ticket",
        "id": ticket["id"],
        "number": ticket["number"],
        "key": ticket["key"],
        "title": "Drucker reparieren",
        "kind": "bug",
        "space_id": desk.space_id,
    }
    assert hit["space_name"] == "Desk"
    assert hit["status"] == ticket["status"]
    assert "⟦Streifen⟧" in hit["snippet"] and hit["score"] > 0
    assert await _ids(desk.viewer, "Drucker") == [ticket["id"]]  # the title too


async def test_a_key_or_a_number_puts_that_ticket_first(desk: Desk) -> None:
    await new_ticket(desk.editor, desk.space_id, "Nummer 5 im Text")
    target = await new_ticket(desk.editor, desk.space_id, "Ziel")
    for q in (target["key"], target["key"].lower(), str(target["number"]), f" {target['key']} "):
        hits = await _hits(desk.viewer, q)
        assert hits and hits[0]["id"] == target["id"], q


async def test_tickets_of_hidden_spaces_are_never_found(desk: Desk, make_space: MakeSpace) -> None:
    """The leak test of the ticket search: by word, key and number, with and without a
    space filter. (Mutation probe: without the ticket scope in the statement, this
    fails.)"""
    secret = await make_space("team", "Geheim")
    hidden = await new_ticket(
        desk.admin, secret.id, "Geheimsache Kolibri", description_md="Kolibri"
    )
    seen = await new_ticket(desk.editor, desk.space_id, "Sichtbar Kolibri")
    for q in ("Kolibri", hidden["key"], str(hidden["number"]), "Geheimsache"):
        assert hidden["id"] not in await _ids(desk.viewer, q), q
        assert hidden["id"] not in await _ids(desk.outsider, q), q
    assert await _ids(desk.viewer, "Kolibri") == [seen["id"]]
    assert await _ids(desk.outsider, "Kolibri") == []
    r = await desk.viewer.get("/api/search", params={"q": "Kolibri", "space_id": str(secret.id)})
    assert r.status_code == 404
    assert set(await _ids(desk.admin, "Kolibri")) == {hidden["id"], seen["id"]}


async def test_losing_the_space_loses_its_tickets_in_the_search(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, "Abschied Wombat")
    assert await _ids(desk.viewer, "Wombat") == [ticket["id"]]
    await SpaceRepository(session).remove_member(
        desk.space.id, Principal.user(desk.users["viewer"].id)
    )
    assert await _ids(desk.viewer, "Wombat") == []


async def test_types_space_and_tags_narrow_tickets(desk: Desk, make_space: MakeSpace) -> None:
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    here = await new_ticket(desk.editor, desk.space_id, "Okapi hier")
    there = await new_ticket(desk.editor, other.id, "Okapi dort")
    page = await publish(desk.editor, await new_page(desk.editor, desk.space_id, "Okapi Seite"))
    assert set(await _ids(desk.editor, "Okapi")) == {here["id"], there["id"], page["id"]}
    assert set(await _ids(desk.editor, "Okapi", types="ticket")) == {here["id"], there["id"]}
    assert await _ids(desk.editor, "Okapi", types="page") == [page["id"]]
    in_space = await _ids(desk.editor, "Okapi", space_id=desk.space_id)
    assert set(in_space) == {here["id"], page["id"]}
    tag = (await desk.admin.post("/api/tags", json={"name": "Zoo"})).json()
    r = await desk.editor.put(
        f"/api/tickets/{here['number']}/tags", json={"tag_ids": [tag["id"]], "version": 1}
    )
    assert r.status_code == 200, r.text
    assert await _ids(desk.editor, "Okapi", tag=tag["id"]) == [here["id"]]


async def test_tickets_pages_and_messages_share_one_cursor(desk: Desk) -> None:
    expected = set()
    for i in range(3):
        ticket = await new_ticket(
            desk.editor, desk.space_id, f"Tapir {i}", description_md="Tapir " * i
        )
        page = await publish(
            desk.editor, await new_page(desk.editor, desk.space_id, f"Tapir Seite {i}")
        )
        expected |= {ticket["id"], page["id"]}
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {
            "q": "Tapir",
            "limit": 2,
            **({"cursor": cursor} if cursor else {}),
        }
        r = await desk.viewer.get("/api/search", params=params)
        assert r.status_code == 200, r.text
        seen += [h["id"] for h in r.json()["items"]]
        if (cursor := r.json()["next_cursor"]) is None:
            break
    assert len(seen) == len(expected) and set(seen) == expected

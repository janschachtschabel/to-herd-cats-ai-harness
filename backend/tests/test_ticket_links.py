"""Links between tickets and wiki pages (plan M4 task 4, decision 11): a ticket links
pages of any space; each side lists only what the caller sees at both ends, filtered
in SQL. A trashed page keeps its links but shows none; purging it removes them."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.tickets import links
from app.modules.tickets.models import TicketPageLink
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket
from tests.factories_wiki import new_page, publish
from tests.page_thread_helpers import messages
from tests.ticket_thread_helpers import ticket_handlers, ticket_thread


async def _link(client: AsyncClient, ticket: dict[str, Any], page: dict[str, Any]) -> Any:
    return await client.put(f"/api/tickets/{ticket['number']}/pages/{page['id']}")


async def _unlink(client: AsyncClient, ticket: dict[str, Any], page: dict[str, Any]) -> Any:
    return await client.delete(f"/api/tickets/{ticket['number']}/pages/{page['id']}")


async def _pages_of(client: AsyncClient, ticket: dict[str, Any], **params: Any) -> list[str]:
    r = await client.get(f"/api/tickets/{ticket['number']}/pages", params=params)
    assert r.status_code == 200, r.text
    return [p["id"] for p in r.json()["items"]]


async def _tickets_of(client: AsyncClient, page: dict[str, Any], **params: Any) -> list[str]:
    r = await client.get(f"/api/pages/{page['id']}/tickets", params=params)
    assert r.status_code == 200, r.text
    return [t["id"] for t in r.json()["items"]]


def _error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


async def _page(desk: Desk, title: str, space_id: object | None = None) -> dict[str, Any]:
    page = await new_page(desk.editor, space_id or desk.space_id, title)
    return await publish(desk.editor, page)


async def test_an_editor_links_and_unlinks_a_page(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id, "Mit Seite")
    page = await _page(desk, "Handbuch")
    assert (await _link(desk.editor, ticket, page)).status_code == 204
    assert (await _link(desk.editor, ticket, page)).status_code == 204  # idempotent
    r = await desk.viewer.get(f"/api/tickets/{ticket['number']}/pages")
    assert r.status_code == 200
    (item,) = r.json()["items"]
    assert {k: item[k] for k in ("id", "space_id", "space_name", "title", "path")} == {
        "id": page["id"],
        "space_id": desk.space_id,
        "space_name": "Desk",
        "title": "Handbuch",
        "path": "handbuch",
    }
    assert item["linked_at"]
    r = await desk.viewer.get(f"/api/pages/{page['id']}/tickets")
    (row,) = r.json()["items"]
    assert (row["id"], row["key"], row["status"]["category"]) == (
        ticket["id"],
        ticket["key"],
        "open",
    )
    assert (await _unlink(desk.editor, ticket, page)).status_code == 204
    assert (await _unlink(desk.editor, ticket, page)).status_code == 204  # idempotent
    assert await _pages_of(desk.viewer, ticket) == []
    assert await _tickets_of(desk.viewer, page) == []
    fields = await session.scalars(
        select(EventOutbox.payload["fields"].astext)
        .where(EventOutbox.type == "ticket.updated")
        .order_by(EventOutbox.id)
    )
    assert list(fields) == ['["page"]', '["page"]']  # one event per real change


async def test_links_appear_in_the_ticket_timeline(desk: Desk, session: AsyncSession) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    page = await _page(desk, "Protokoll")
    await _link(desk.editor, ticket, page)
    await _unlink(desk.editor, ticket, page)
    for _ in range(2):
        await ticket_handlers(session)
    thread = await ticket_thread(desk.viewer, ticket)
    entries = [m["system"] for m in await messages(desk.viewer, thread["id"])]
    assert [e["key"] for e in entries] == [
        "ticket.created",
        "ticket.page_linked",
        "ticket.page_unlinked",
    ]
    named = {"value": page["id"], "name": "Protokoll"}
    assert (entries[1]["old"], entries[1]["new"]) == (None, named)
    assert (entries[2]["old"], entries[2]["new"]) == (named, None)


async def test_a_timeline_entry_names_no_page_its_reader_cannot_see(
    desk: Desk, session: AsyncSession, make_space: MakeSpace
) -> None:
    secret = await make_space("team", "Geheim", members=[(desk.users["editor"], "editor")])
    page = await _page(desk, "Geheimplan", secret.id)
    ticket = await new_ticket(desk.editor, desk.space_id)
    assert (await _link(desk.editor, ticket, page)).status_code == 204
    await ticket_handlers(session)
    thread = await ticket_thread(desk.viewer, ticket)
    seen = [m["system"] for m in await messages(desk.editor, thread["id"])]
    assert seen[1]["new"] == {"value": page["id"], "name": "Geheimplan"}
    unseen = [m["system"] for m in await messages(desk.viewer, thread["id"])]
    assert unseen[1]["key"] == "ticket.page_linked"
    assert unseen[1]["new"] is None  # neither the title nor the id


async def test_rights_to_link(desk: Desk, make_space: MakeSpace) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    page = await _page(desk, "Seite")
    _error(await _link(desk.viewer, ticket, page), 403, "auth.permission_denied")
    _error(await _unlink(desk.viewer, ticket, page), 403, "auth.permission_denied")
    _error(await _link(desk.outsider, ticket, page), 404, "ticket.not_found")
    _error(
        await desk.outsider.get(f"/api/tickets/{ticket['number']}/pages"), 404, "ticket.not_found"
    )
    _error(await desk.outsider.get(f"/api/pages/{page['id']}/tickets"), 404, "page.not_found")
    secret = await make_space("team", "Geheim")
    hidden = await new_page(desk.admin, secret.id, "Versteckt")
    _error(await _link(desk.editor, ticket, hidden), 404, "page.not_found")
    _error(await _unlink(desk.editor, ticket, hidden), 404, "page.not_found")
    draft = await new_page(desk.editor, desk.space_id, "Entwurf")
    assert (await _link(desk.editor, ticket, draft)).status_code == 204
    free = await desk.editor.put(f"/api/tickets/999999/pages/{page['id']}")
    _error(free, 404, "ticket.not_found")


async def test_each_side_lists_only_what_both_ends_let_the_caller_see(
    desk: Desk, make_space: MakeSpace
) -> None:
    """The leak test of links, in both directions. (Mutation probes: without the page
    visibility in the ticket's page list, or without the ticket scope in the page's
    ticket list, this fails.)"""
    reader = desk.users["outsider"]  # sees the secret space, not the desk
    secret = await make_space(
        "team", "Geheim", members=[(desk.users["editor"], "editor"), (reader, "viewer")]
    )
    secret_page = await _page(desk, "Geheimseite", secret.id)
    desk_page = await _page(desk, "Deskseite")
    draft = await new_page(desk.editor, desk.space_id, "Entwurf")
    ticket = await new_ticket(desk.editor, desk.space_id, "Deskticket")
    secret_ticket = await new_ticket(desk.editor, secret.id, "Geheimticket")
    for page in (secret_page, desk_page, draft):
        assert (await _link(desk.editor, ticket, page)).status_code == 204
    assert (await _link(desk.editor, secret_ticket, desk_page)).status_code == 204
    assert (await _link(desk.editor, secret_ticket, secret_page)).status_code == 204

    # A desk viewer sees the desk ticket, but neither the secret page nor the draft.
    assert await _pages_of(desk.viewer, ticket) == [desk_page["id"]]
    assert await _tickets_of(desk.viewer, desk_page) == [ticket["id"]]
    # The secret space's reader sees the secret page, not the desk ticket.
    assert await _tickets_of(desk.outsider, secret_page) == [secret_ticket["id"]]
    assert await _pages_of(desk.outsider, secret_ticket) == [secret_page["id"]]
    # Someone seeing both ends sees every link.
    assert set(await _pages_of(desk.editor, ticket)) == {
        secret_page["id"],
        desk_page["id"],
        draft["id"],
    }
    assert set(await _tickets_of(desk.editor, desk_page)) == {ticket["id"], secret_ticket["id"]}


async def test_trash_hides_links_restore_brings_them_back_purge_removes_them(
    desk: Desk, session: AsyncSession
) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    page = await _page(desk, "Kurzlebig")
    await _link(desk.editor, ticket, page)
    fresh = (await desk.editor.get(f"/api/pages/{page['id']}")).json()
    r = await desk.moderator.post(
        f"/api/pages/{page['id']}/trash", json={"version": fresh["version"]}
    )
    assert r.status_code == 204
    assert await _pages_of(desk.editor, ticket) == []
    _error(await desk.editor.get(f"/api/pages/{page['id']}/tickets"), 404, "page.not_found")
    assert (await desk.moderator.post(f"/api/pages/{page['id']}/restore")).status_code == 200
    assert await _pages_of(desk.editor, ticket) == [page["id"]]
    fresh = (await desk.editor.get(f"/api/pages/{page['id']}")).json()
    await desk.moderator.post(f"/api/pages/{page['id']}/trash", json={"version": fresh["version"]})
    assert (await desk.admin.delete(f"/api/pages/{page['id']}")).status_code == 204
    assert await session.scalar(select(func.count()).select_from(TicketPageLink)) == 0


async def test_both_lists_are_paginated(desk: Desk) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    pages = [await _page(desk, f"Seite {i}") for i in range(3)]
    tickets = [await new_ticket(desk.editor, desk.space_id, f"T{i}") for i in range(3)]
    for page in pages:
        await _link(desk.editor, ticket, page)
    for other in tickets:
        await _link(desk.editor, other, pages[0])
    seen: list[str] = []
    cursor = None
    while True:
        params: dict[str, Any] = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        r = await desk.viewer.get(f"/api/tickets/{ticket['number']}/pages", params=params)
        seen += [p["id"] for p in r.json()["items"]]
        if (cursor := r.json()["next_cursor"]) is None:
            break
    assert seen == [p["id"] for p in reversed(pages)]  # last linked first
    numbers: list[int] = []
    cursor = None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        r = await desk.viewer.get(f"/api/pages/{pages[0]['id']}/tickets", params=params)
        numbers += [t["number"] for t in r.json()["items"]]
        if (cursor := r.json()["next_cursor"]) is None:
            break
    assert numbers == sorted([ticket["number"], *(t["number"] for t in tickets)], reverse=True)
    bad = await desk.viewer.get(f"/api/pages/{pages[0]['id']}/tickets", params={"cursor": "x"})
    assert bad.status_code == 422


async def test_a_ticket_links_at_most_so_many_pages(
    desk: Desk, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(links, "MAX_LINKS", 2)
    ticket = await new_ticket(desk.editor, desk.space_id)
    pages = [await _page(desk, f"Seite {i}") for i in range(3)]
    for page in pages[:2]:
        assert (await _link(desk.editor, ticket, page)).status_code == 204
    _error(await _link(desk.editor, ticket, pages[2]), 422, "ticket.too_many_pages")
    assert (await _link(desk.editor, ticket, pages[1])).status_code == 204  # already there

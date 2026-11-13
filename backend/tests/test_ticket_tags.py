"""Tags on tickets (plan M4 task 4): system-wide tags and tags of the ticket's space,
set with `ticket.edit` and the version read; the list filters by them; deleting a tag
takes it off tickets too."""

from typing import Any

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import EventOutbox
from app.modules.tags.models import Tagging
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket
from tests.page_thread_helpers import messages
from tests.ticket_thread_helpers import ticket_handlers, ticket_thread


async def _tag(client: AsyncClient, name: str, space_id: object | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"name": name}
    if space_id is not None:
        body["space_id"] = str(space_id)
    r = await client.post("/api/tags", json=body)
    assert r.status_code == 201, r.text
    tag: dict[str, Any] = r.json()
    return tag


async def _set(client: AsyncClient, ticket: dict[str, Any], *tags: dict[str, Any]) -> Any:
    return await client.put(
        f"/api/tickets/{ticket['number']}/tags",
        json={"tag_ids": [t["id"] for t in tags], "version": ticket["version"]},
    )


def _error(response: Any, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


async def _titles(client: AsyncClient, **params: Any) -> list[str]:
    r = await client.get("/api/tickets", params=params)
    assert r.status_code == 200, r.text
    return [t["title"] for t in r.json()["items"]]


async def test_an_editor_tags_a_ticket(desk: Desk, session: AsyncSession) -> None:
    system = await _tag(desk.admin, "Dringend")
    local = await _tag(desk.moderator, "Abrechnung", desk.space_id)
    ticket = await new_ticket(desk.editor, desk.space_id, "Getaggt")
    assert ticket["tags"] == []
    r = await _set(desk.editor, ticket, system, local, system)
    assert r.status_code == 200, r.text
    tagged = r.json()
    assert [t["name"] for t in tagged["tags"]] == ["Abrechnung", "Dringend"]
    assert tagged["version"] == ticket["version"] + 1
    got = (await desk.viewer.get(f"/api/tickets/{ticket['number']}")).json()
    assert [t["id"] for t in got["tags"]] == [local["id"], system["id"]]
    (row,) = (await desk.viewer.get("/api/tickets")).json()["items"]
    assert [t["name"] for t in row["tags"]] == ["Abrechnung", "Dringend"]
    _error(await _set(desk.editor, ticket, system), 409, "ticket.version_conflict")
    fields = await session.scalars(
        select(EventOutbox.payload["fields"].astext).where(EventOutbox.type == "ticket.updated")
    )
    assert list(fields) == ['["tags"]']
    await ticket_handlers(session)  # a tag change writes no timeline entry
    thread = await ticket_thread(desk.viewer, ticket)
    keys = [m["system"]["key"] for m in await messages(desk.viewer, thread["id"])]
    assert keys == ["ticket.created"]


async def test_tagging_needs_edit_and_a_tag_of_the_space(desk: Desk, make_space: MakeSpace) -> None:
    ticket = await new_ticket(desk.editor, desk.space_id)
    other = await make_space("team", "Anders", members=[(desk.users["editor"], "editor")])
    elsewhere = await _tag(desk.admin, "Anderswo", other.id)
    hidden_space = await make_space("team", "Versteckt")
    hidden = await _tag(desk.admin, "Versteckt", hidden_space.id)
    mine = await _tag(desk.admin, "Hier", desk.space_id)
    _error(await _set(desk.viewer, ticket, mine), 403, "auth.permission_denied")
    _error(await _set(desk.outsider, ticket, mine), 404, "ticket.not_found")
    _error(await _set(desk.editor, ticket, elsewhere), 422, "tags.wrong_space")
    _error(await _set(desk.editor, ticket, hidden), 422, "tags.not_found")
    many = [await _tag(desk.admin, f"T{i}") for i in range(21)]
    r = await _set(desk.editor, ticket, *many)
    assert r.status_code == 422
    assert (await _set(desk.editor, ticket, *many[:20])).status_code == 200


async def test_the_list_filters_by_every_tag_given(desk: Desk) -> None:
    a = await _tag(desk.admin, "A")
    b = await _tag(desk.admin, "B")
    both = await new_ticket(desk.editor, desk.space_id, "Beide")
    only_a = await new_ticket(desk.editor, desk.space_id, "Nur A")
    await new_ticket(desk.editor, desk.space_id, "Keins")
    assert (await _set(desk.editor, both, a, b)).status_code == 200
    assert (await _set(desk.editor, only_a, a)).status_code == 200
    assert sorted(await _titles(desk.viewer, tag=a["id"])) == ["Beide", "Nur A"]
    assert await _titles(desk.viewer, tag=[a["id"], b["id"]]) == ["Beide"]


async def test_a_hidden_space_s_tagged_tickets_stay_hidden(
    desk: Desk, make_space: MakeSpace
) -> None:
    tag = await _tag(desk.admin, "Überall")
    secret = await make_space("team", "Geheim")
    hidden = await new_ticket(desk.admin, secret.id, "Geheim")
    assert (await _set(desk.admin, hidden, tag)).status_code == 200
    assert await _titles(desk.viewer, tag=tag["id"]) == []
    assert await _titles(desk.admin, tag=tag["id"]) == ["Geheim"]


async def test_deleting_a_tag_takes_it_off_tickets(desk: Desk, session: AsyncSession) -> None:
    tag = await _tag(desk.moderator, "Weg", desk.space_id)
    ticket = await new_ticket(desk.editor, desk.space_id)
    assert (await _set(desk.editor, ticket, tag)).status_code == 200
    assert (await desk.moderator.delete(f"/api/tags/{tag['id']}")).status_code == 204
    assert (await desk.viewer.get(f"/api/tickets/{ticket['number']}")).json()["tags"] == []
    assert await session.scalar(select(func.count()).select_from(Tagging)) == 0

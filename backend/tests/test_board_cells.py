"""The board's card statements (module review M4b, finding 5): the daily view takes at
most 20 tickets per cell (422 above, as every other limit of the board answers), the
plain board's columns up to 100; neither loads the descriptions it never returns."""

from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories_tickets import Desk, new_ticket
from tests.test_ticket_views import _counting


async def test_the_daily_takes_at_most_twenty_per_cell(desk: Desk) -> None:
    url = f"/api/spaces/{desk.space_id}/board"
    r = await desk.viewer.get(url, params={"group_by": "assignee", "limit": 21})
    assert (r.status_code, r.json()["error"]["code"]) == (422, "validation_failed")
    r = await desk.viewer.get(url, params={"group_by": "assignee", "limit": 20})
    assert r.status_code == 200, r.text
    r = await desk.viewer.get(url, params={"limit": 100})
    assert r.status_code == 200, r.text


async def test_the_cards_leave_the_description_unloaded(desk: Desk, session: AsyncSession) -> None:
    await new_ticket(desk.editor, desk.space_id, "Karte", description_md="Lang " * 200)
    url = f"/api/spaces/{desk.space_id}/board"
    for params in ({}, {"group_by": "assignee"}):
        with _counting(session) as statements:
            r = await desk.viewer.get(url, params=params)
        assert r.status_code == 200, r.text
        assert statements
        assert not [s for s in statements if "work_item.description_md" in s], params

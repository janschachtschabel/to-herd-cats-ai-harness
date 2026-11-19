"""The overlays as an output path (plan M10 review focus 2 names them): they hold
ticket due dates, sprints and automation terms, never an event, so nothing of the
private event reaches anyone through them. A guard from the review of task 9: it
passes at 36954d7 and fails once overlays start to carry events."""

from tests.factories_calendar import SECRET, PrivateEvent

URL = "/api/calendar/overlays"


async def test_a_private_event_reaches_nobody_through_the_overlays(
    private_event: PrivateEvent,
) -> None:
    case = private_event
    for client in (case.organiser_client, case.reader_client, case.outsider_client):
        r = await client.get(URL, params={"from": "1900-01-01", "to": "2400-01-01", "limit": 100})
        assert r.status_code == 200, r.text
        assert SECRET not in r.text
        assert str(case.event["id"]) not in r.text
        assert r.json()["next_cursor"] is None

"""What an automation shows of its place and its owner's words (review M7, finding 2;
as the run view does, M6): the instruction, a channel's name and a ticket's number
only to its owner and to whoever may read its place now (a channel or a ticket's
thread as the conversation rules say; a DM: its owner alone). Anyone else who sees
the automation (the agent's responsible person outside the space, `agent.manage`)
gets those fields null and `redacted` true, in the view and in the lists. An admin who
reads the place by admin right reads it in full and is noted (`space.admin_access`),
as for any read of that space."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select

from app.core.principal import SystemRole
from app.modules.audit.models import ADMIN_ACCESS, AuditLog
from tests.conftest import MakeClient
from tests.factories import MakeUser, login
from tests.factories_writing import Work
from tests.test_automation_api import BASE, DAILY, SECRET, body, channel, clock, make, manage

__all__ = ["clock"]


async def test_the_responsible_person_outside_the_space_reads_neither_place_nor_words(
    work: Work,
) -> None:
    """Carol is the agent's responsible person and in no space. She may learn that an
    automation of her agent exists (to pause notices, decision 2), but not the name of
    a channel she cannot see, the number of a ticket that answers her 404, nor the
    owner's words (the run view redacts the same for her, M6)."""
    bench = work.bench
    bench.agent.responsible_user_id = bench.people.users["carol"].id
    await bench.session.flush()
    alice, carol = bench.people.alice, bench.people.carol
    r = await work.admin.post(f"/api/spaces/{work.space.id}/channels", json={"name": "fusion-x"})
    assert r.status_code == 201, r.text
    in_channel = await make(
        alice, body(work, {"type": "channel", "conversation_id": r.json()["id"]}, DAILY)
    )
    ticket = await work.ticket("Geheimes Ticket")
    in_ticket = await make(
        alice, body(work, {"type": "ticket", "ticket_number": ticket["number"]}, DAILY)
    )
    assert (await carol.get(f"/api/spaces/{work.space.id}")).status_code == 404
    assert (await carol.get(f"/api/tickets/{ticket['number']}")).status_code == 404
    shown = (await carol.get(f"{BASE}/{in_channel['id']}")).json()
    on_ticket = (await carol.get(f"{BASE}/{in_ticket['id']}")).json()
    leaks = {
        "channel name": shown.get("place", {}).get("name") == "fusion-x",
        "instruction": shown.get("instruction") == SECRET,
        "ticket number": on_ticket.get("place", {}).get("ticket_number") == ticket["number"],
    }
    assert not any(leaks.values()), leaks
    assert (shown["redacted"], on_ticket["redacted"]) == (True, True)
    assert (shown["instruction"], on_ticket["place"]["ticket_number"]) == (None, None)
    assert shown["place"]["type"] == "channel"  # what kind of place it is stays
    for made, client in ((in_channel, alice), (in_ticket, alice)):
        own = (await client.get(f"{BASE}/{made['id']}")).json()
        assert (own["redacted"], own["instruction"]) == (False, SECRET)


async def test_the_responsible_person_reads_no_words_of_someone_elses_dm(work: Work) -> None:
    """An automation in Alice's DM with the agent holds her words to the agent in a
    DM: the agent's responsible person does not read DMs (only the audited inspection
    does)."""
    bench = work.bench
    bench.agent.responsible_user_id = bench.people.users["carol"].id
    await bench.session.flush()
    made = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    r = await bench.people.carol.get(f"{BASE}/{made['id']}")
    assert SECRET not in r.text, "the owner's DM instruction is shown to the responsible person"
    assert r.json()["redacted"] is True


async def test_who_may_read_the_place_reads_it_in_full(work: Work) -> None:
    """A manager of the space (not the owner) reads the channel's automation in full,
    in the view and in the space's list."""
    await manage(work, "bob")
    place = {"type": "channel", "conversation_id": await channel(work)}
    made = await make(work.bench.people.alice, body(work, place, DAILY))
    bob = work.bench.people.bob
    shown = (await bob.get(f"{BASE}/{made['id']}")).json()
    assert (shown["redacted"], shown["instruction"]) == (False, SECRET)
    listed = (await bob.get(f"/api/spaces/{work.space.id}/automations")).json()["items"]
    assert [(a["redacted"], a["instruction"]) for a in listed] == [(False, SECRET)]


async def _agent_manager(work: Work, make_user: MakeUser, make_client: MakeClient) -> AsyncClient:
    """A system owner in no space: `agent.manage`, a team space only by admin right."""
    user = await make_user(SystemRole.OWNER)
    client = await make_client(csrf=True)
    await login(client, user.email)
    return client


async def test_an_admin_reads_a_channels_words_by_admin_right_and_is_noted_but_no_dm(
    work: Work, make_user: MakeUser, make_client: MakeClient
) -> None:
    bench = work.bench
    place = {"type": "channel", "conversation_id": await channel(work)}
    in_channel = await make(bench.people.alice, body(work, place, DAILY))
    in_dm = await make(bench.people.alice, body(work, {"type": "dm"}, DAILY))
    owner = await _agent_manager(work, make_user, make_client)
    shown = (await owner.get(f"{BASE}/{in_channel['id']}")).json()
    assert (shown["redacted"], shown["instruction"]) == (False, SECRET)
    me = uuid.UUID((await owner.get("/api/auth/me")).json()["user"]["id"])
    noted = await bench.session.scalars(
        select(AuditLog.target_id).where(AuditLog.action == ADMIN_ACCESS, AuditLog.actor_id == me)
    )
    assert list(noted) == [work.space.id]
    listed = (await owner.get(f"/api/agents/{bench.agent.id}/automations")).json()["items"]
    by_id = {a["id"]: (a["redacted"], a["instruction"]) for a in listed}
    assert by_id == {in_channel["id"]: (False, SECRET), in_dm["id"]: (True, None)}

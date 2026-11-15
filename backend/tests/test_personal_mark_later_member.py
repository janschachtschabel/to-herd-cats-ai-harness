"""Module review M8 4, K1: a team space where the asking person is the only member
today is no place to write her personal content without her release: an admin (or
she) may add a member at any time, and what was written there carries no mark. So a
marked run's ticket there waits for her release, and a member added later reads
nothing she did not release."""

from app.modules.agents.run_models import StopReason
from tests.factories_external import Ext, call
from tests.factories_personal import asks_release, decide
from tests.factories_writing import Work, alone_in
from tests.test_run_external_personal import SECRET, _personal


async def _titles(work: Work, who: str) -> list[str]:
    client = getattr(work.bench.people, who)
    r = await client.get("/api/tickets", params={"space_id": str(work.space.id)})
    assert r.status_code == 200, r.text
    return [t["title"] for t in r.json()["items"]]


async def test_a_later_member_never_reads_what_she_did_not_release(ext: Ext, work: Work) -> None:
    name = await _personal(ext)
    await alone_in(work)  # the team space "Werkstatt": Alice is its only person today
    ext.bench.stub.state.replies.extend(
        [
            call(name, q="meine"),
            call("create_ticket", space_id=str(work.space.id), title=f"Fund {SECRET}"),
            {"content": "Angelegt."},
        ]
    )
    await ext.bench.say("Such meine Issues und leg ein Ticket an")
    approval = await asks_release(ext, await ext.bench.run_next())
    await decide(ext, approval, "reject")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    # the space's admin by admin right adds Bob, as an admin may at any time
    bob = ext.bench.people.users["bob"]
    member = {"member_type": "user", "member_id": str(bob.id), "role": "viewer"}
    r = await work.admin.put(f"/api/spaces/{work.space.id}/members", json=member)
    assert r.status_code == 200, r.text
    assert not any(SECRET in t for t in await _titles(work, "bob"))
    assert not any(SECRET in t for t in await _titles(work, "alice"))

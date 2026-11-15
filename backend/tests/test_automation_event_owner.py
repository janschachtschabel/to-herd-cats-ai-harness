"""An event rule is for those who manage its space (plan M7 decisions 2, 8 and 12):
making one, changing one, taking one over and keeping one all need `space.manage` in
the space of its place (`standing.may_own` knows the kind). A manager who is demoted
loses her rules: at the next term the rule pauses (`owner`), as for any right an
automation needs; `abilities` offer nothing the action would refuse."""

import uuid
from typing import Any

from app.core.permissions import SpaceRole
from app.core.principal import Principal
from app.modules.spaces.repository import SpaceRepository
from tests.factories_automations import T0, notified, reload, runs_of
from tests.factories_writing import Work
from tests.test_automation_api import BASE, body, channel, clock, make, manage
from tests.test_automation_events import take_in

__all__ = ["clock"]

RULE = {"kind": "event", "event_type": "ticket.created"}


async def _role(work: Work, who: str, role: SpaceRole) -> None:
    user = work.bench.people.users[who]
    await SpaceRepository(work.bench.session).set_member(
        work.space.id, Principal.user(user.id), role
    )


async def _rule(work: Work) -> dict[str, Any]:
    """Alice manages the space and owns an event rule in one of its channels."""
    await manage(work)
    place = {"type": "channel", "conversation_id": await channel(work)}
    return await make(work.bench.people.alice, body(work, place, RULE))


async def test_taking_an_event_rule_over_needs_space_manage(work: Work) -> None:
    """Carol is the agent's responsible person (so she sees the rule) and an editor of
    the space: she could not make an event rule there (403), so she may not take one
    over either (decision 2: "wer die Aufgabe selbst anlegen dürfte")."""
    made = await _rule(work)
    work.bench.agent.responsible_user_id = work.bench.people.users["carol"].id
    await _role(work, "carol", SpaceRole.EDITOR)
    await work.bench.session.flush()
    carol = work.bench.people.carol
    place = made["place"]["conversation_id"]
    own = await carol.post(
        BASE, json=body(work, {"type": "channel", "conversation_id": place}, RULE)
    )
    assert own.status_code == 403, own.text  # she may not make one
    seen = await carol.get(f"{BASE}/{made['id']}")
    assert seen.status_code == 200, seen.text
    taken = await carol.post(f"{BASE}/{made['id']}/take-over", json={"version": made["version"]})
    assert (seen.json()["abilities"]["take_over"], taken.status_code) == (False, 403), taken.text
    await _role(work, "carol", SpaceRole.ADMIN)  # once she manages the space, she may
    seen = await carol.get(f"{BASE}/{made['id']}")
    assert seen.json()["abilities"]["take_over"] is True
    taken = await carol.post(f"{BASE}/{made['id']}/take-over", json={"version": made["version"]})
    assert taken.status_code == 200, taken.text


async def test_an_event_rule_does_not_run_on_for_an_owner_who_manages_no_more(work: Work) -> None:
    """Alice loses `space.manage` (she stays an editor): her rule must not start runs
    any more (paused `owner`, like any right an automation needs, decision 2), the
    space's managers hear of it, and nobody may resume it while she cannot run it."""
    made = await _rule(work)
    await _role(work, "alice", SpaceRole.EDITOR)
    await work.ticket("Neu")
    await take_in(work.bench, "ticket.created", T0)
    rule = await reload(work.bench.session, uuid.UUID(made["id"]))
    runs = await runs_of(work.bench.session, rule.id)
    assert (len(runs), rule.state, rule.paused_reason) == (0, "paused", "owner")
    admin = work.bench.people.users["admin"]
    assert (admin.id, "automation") in await notified(work.bench.session, rule.id)
    seen = await work.admin.get(f"{BASE}/{made['id']}")
    assert seen.json()["abilities"]["resume"] is False
    r = await work.admin.post(f"{BASE}/{made['id']}/resume", json={"version": rule.version})
    assert r.status_code == 409 and r.json()["error"]["code"] == "automation.owner_unable"


async def test_an_editor_changing_her_rule_is_refused_as_she_is_offered(work: Work) -> None:
    """Demoted, Alice may no longer change her rule's words (403), and `abilities.edit`
    says so before she tries."""
    made = await _rule(work)
    await _role(work, "alice", SpaceRole.EDITOR)
    alice = work.bench.people.alice
    seen = await alice.get(f"{BASE}/{made['id']}")
    r = await alice.patch(
        f"{BASE}/{made['id']}", json={"version": made["version"], "instruction": "Neu."}
    )
    assert (seen.json()["abilities"]["edit"], r.status_code) == (False, 403), r.text

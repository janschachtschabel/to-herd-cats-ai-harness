"""Every role against every action on an automation (plan M7 decision 12, task 7), as
one table. Alice owns an automation in a channel of the space; around it: another
editor of the space, a viewer, a manager of the space, someone with `agent.manage`
(a system owner in no space), a system admin, a manager of the space without
`ai.use`, the agent's responsible person (in no space) and the owner of another
organisation (through the services: login knows the installation's one organisation
only). Who may not see it gets 404 like an unknown id; who sees it but may not
do the action gets 403."""

import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.automations.control import AutomationControl
from app.modules.automations.schemas import AutomationUpdate
from app.modules.automations.service import AutomationService
from app.modules.orgs.models import Organization
from app.modules.spaces.repository import SpaceRepository
from tests.conftest import MakeClient
from tests.factories import MakeUser, login
from tests.factories_writing import Work
from tests.test_automation_api import BASE, DAILY, body, channel, clock, make
from tests.test_automation_changes import post

__all__ = ["clock"]

OK, SHOWN, HIDDEN = (200, None), "shown", "hidden"
GONE = (404, "automation.not_found")
NOT_ALLOWED = (403, "automation.not_allowed")
NO_AI = (404, "ai.not_found")
NO_AGENT = (404, "agent.not_found")
NO_SPACE = (404, "space.not_found")
ACTIONS = ("get", "firings", "update", "pause", "resume", "delete", "run", "take_over")
LISTS = ("mine", "agent", "space")
# role: answers to ACTIONS, then what LISTS show
TABLE: dict[str, tuple[tuple[Any, ...], tuple[Any, ...]]] = {
    "owner": ((OK, OK, OK, OK, OK, OK, OK, OK), (SHOWN, NO_AGENT, SHOWN)),
    "member": ((GONE,) * 8, (HIDDEN, NO_AGENT, HIDDEN)),
    "viewer": ((GONE,) * 8, (HIDDEN, NO_AGENT, HIDDEN)),
    "manager": ((OK, OK, NOT_ALLOWED, OK, OK, OK, NOT_ALLOWED, OK), (HIDDEN, NO_AGENT, SHOWN)),
    "agent_manage": ((OK, OK, NOT_ALLOWED, OK, OK, OK, NOT_ALLOWED, OK), (HIDDEN, SHOWN, SHOWN)),
    "admin": ((OK, OK, NOT_ALLOWED, OK, OK, OK, NOT_ALLOWED, OK), (HIDDEN, SHOWN, SHOWN)),
    "no_ai": ((GONE,) * 8, (NO_AI, NO_AGENT, NO_AI)),
    "responsible": (
        (OK, OK, NOT_ALLOWED, NOT_ALLOWED, NOT_ALLOWED, NOT_ALLOWED, NOT_ALLOWED, NOT_ALLOWED),
        (HIDDEN, NO_AGENT, NO_SPACE),
    ),
}


async def _cast(work: Work, make_user: MakeUser, make_client: MakeClient) -> dict[str, Any]:
    """The clients of every role; the agent's responsible person is Carol."""
    bench, session = work.bench, work.bench.session
    spaces = SpaceRepository(session)

    async def person(role: SystemRole, space_role: SpaceRole | None, **more: Any) -> AsyncClient:
        user = await make_user(role, **more)
        if space_role is not None:
            await spaces.set_member(work.space.id, Principal.user(user.id), space_role)
        client = await make_client(csrf=True)
        await login(client, user.email)
        return client

    bob = bench.people.users["bob"]
    await spaces.set_member(work.space.id, Principal.user(bob.id), SpaceRole.EDITOR)
    bench.agent.responsible_user_id = bench.people.users["carol"].id
    cast = {
        "owner": bench.people.alice,
        "member": bench.people.bob,
        "viewer": await person(SystemRole.MEMBER, SpaceRole.VIEWER),
        "manager": await person(SystemRole.MEMBER, SpaceRole.ADMIN),
        "agent_manage": await person(SystemRole.OWNER, None),
        "admin": bench.people.admin,
        "no_ai": await person(SystemRole.MEMBER, SpaceRole.ADMIN),
        "responsible": bench.people.carol,
    }
    no_ai = (await cast["no_ai"].get("/api/auth/me")).json()["user"]["id"]
    r = await bench.people.admin.put(
        f"/api/ai/assignments/users/{no_ai}", json={"no_ai": True, "version": None}
    )
    assert r.status_code == 200, r.text
    return cast


async def _act(work: Work, client: AsyncClient, made: dict[str, Any], action: str) -> Response:
    path = f"{BASE}/{made['id']}"
    if action == "get":
        return await client.get(path)
    if action == "firings":
        return await client.get(f"{path}/firings")
    if action == "update":
        return await client.patch(path, json={"version": made["version"], "instruction": "Neu"})
    if action == "resume":
        paused = await post(work.bench.people.alice, made, "pause")
        assert paused.status_code == 200, paused.text
        return await post(client, paused.json(), "resume")
    if action == "delete":
        return await client.delete(f"{path}?version={made['version']}")
    if action == "run":
        return await client.post(f"{path}/run")
    return await post(client, made, action.replace("_", "-"))


def _answers(r: Response, expected: tuple[int, str | None]) -> None:
    status, code = expected
    if code is None:
        assert r.status_code in (200, 204), r.text
    else:
        assert (r.status_code, r.json()["error"]["code"]) == (status, code), r.text


async def _listed(work: Work, client: AsyncClient, which: str) -> Response:
    path = {
        "mine": BASE,
        "agent": f"/api/agents/{work.bench.agent.id}/automations",
        "space": f"/api/spaces/{work.space.id}/automations",
    }[which]
    return await client.get(path)


@pytest.mark.parametrize("role", list(TABLE))
async def test_each_role_may_do_what_the_table_says(
    work: Work, make_user: MakeUser, make_client: MakeClient, role: str
) -> None:
    cast = await _cast(work, make_user, make_client)
    place = {"type": "channel", "conversation_id": await channel(work)}
    actions, lists = TABLE[role]
    for action, expected in zip(ACTIONS, actions, strict=True):
        made = await make(work.bench.people.alice, body(work, place, DAILY))
        _answers(await _act(work, cast[role], made, action), expected)
    shown = await make(work.bench.people.alice, body(work, place, DAILY))
    for which, expected in zip(LISTS, lists, strict=True):
        r = await _listed(work, cast[role], which)
        if expected in (SHOWN, HIDDEN):
            assert r.status_code == 200, r.text
            ids = {item["id"] for item in r.json()["items"]}
            assert (shown["id"] in ids) is (expected == SHOWN), (which, r.text)
        else:
            _answers(r, expected)


async def test_someone_of_another_organisation_finds_nothing(
    work: Work, make_user: MakeUser
) -> None:
    """The owner of another organisation holds `agent.manage` there, and nothing here."""
    session = work.bench.session
    place = {"type": "channel", "conversation_id": await channel(work)}
    made = await make(work.bench.people.alice, body(work, place, DAILY))
    other = Organization(name="Andere")
    session.add(other)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other)
    actor = Actor(other.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    the_id, page = uuid.UUID(made["id"]), PageParams()
    service, control = AutomationService(session), AutomationControl(session)
    calls: list[tuple[str, Callable[[], Awaitable[object]]]] = [
        ("automation.not_found", lambda: service.get(actor, the_id)),
        ("automation.not_found", lambda: service.log(actor, the_id, page)),
        (
            "automation.not_found",
            lambda: service.update(actor, the_id, AutomationUpdate(version=1, instruction="x")),
        ),
        ("automation.not_found", lambda: control.pause(actor, the_id, 1)),
        ("automation.not_found", lambda: control.resume(actor, the_id, 1)),
        ("automation.not_found", lambda: control.delete(actor, the_id, 1)),
        ("automation.not_found", lambda: control.run_now(actor, the_id)),
        ("automation.not_found", lambda: control.take_over(actor, the_id, 1)),
        ("agent.not_found", lambda: service.of_agent(actor, work.bench.agent.id, page)),
        ("space.not_found", lambda: service.of_space(actor, work.space.id, page)),
    ]
    for code, call in calls:
        with pytest.raises(NotFound) as refused:
            await call()
        assert refused.value.code == code
    assert (await service.mine(actor, page)).items == []

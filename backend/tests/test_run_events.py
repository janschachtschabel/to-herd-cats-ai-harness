"""Who reads what of a run's events (module review 1, finding 1; spec 5.5): the asking
person reads their own run in full. Anyone else the run is visible to (the agent's
responsible person, holders of `agent.manage`) reads a tool result only while they
may read every space it came from; otherwise the event comes redacted, with its tool
name and step. An admin reading by admin right gets the content and the same
`space.admin_access` entry a direct page read writes. The model's own words (its text
and arguments) are the conversation's content: only the asking person reads them."""

from typing import Any

from sqlalchemy import func, select

from app.core.permissions import SpaceRole
from app.modules.agents.models import RunEvent, StopReason
from app.modules.audit.models import ADMIN_ACCESS, AuditLog
from app.modules.spaces.models import Space, SpaceKind
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_wiki import new_page, publish

SECRET = "Okapi77"
ANSWER = "AnswerWord42"


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


async def read_run(bench: Bench, make_space: MakeSpace, *members: str) -> tuple[Space, str]:
    """Alice's run that reads a page of a team space (members: Alice, `members`)."""
    users = bench.people.users
    roster = [(users["alice"], SpaceRole.EDITOR), *((users[m], SpaceRole.VIEWER) for m in members)]
    space = await make_space(SpaceKind.TEAM, members=roster)
    await bench.join(space)
    alice = bench.people.alice
    page = await publish(alice, await new_page(alice, space.id, "Plan", content_md=SECRET))
    bench.stub.state.replies.extend([call("read_page", page_id=page["id"]), {"content": ANSWER}])
    posted = await bench.say("Read the plan")
    assert await bench.run_next() == StopReason.COMPLETED
    return space, str(posted["agent_run"]["id"])


async def events(bench: Bench, who: str, run_id: str) -> list[dict[str, Any]]:
    r = await getattr(bench.people, who).get(f"/api/runs/{run_id}/events")
    assert r.status_code == 200, r.text
    items: list[dict[str, Any]] = r.json()["items"]
    return items


def of_kind(items: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [e for e in items if e["kind"] == kind]


async def admin_entries(bench: Bench, space: Space) -> int:
    stmt = select(func.count()).where(
        AuditLog.action == ADMIN_ACCESS, AuditLog.target_id == space.id
    )
    return int(await bench.session.scalar(stmt) or 0)


async def make_responsible(bench: Bench, who: str) -> None:
    bench.agent.responsible_user_id = bench.people.users[who].id
    await bench.session.flush()


async def test_the_asking_person_reads_their_run_in_full(
    bench: Bench, make_space: MakeSpace
) -> None:
    _, run_id = await read_run(bench, make_space)
    items = await events(bench, "alice", run_id)
    assert not any(e["redacted"] for e in items)
    tool = of_kind(items, "tool_call")[0]
    assert SECRET in tool["content"]["text"] and tool["content"]["args"]
    assert any(e["content"].get("text") == ANSWER for e in of_kind(items, "model_call"))


async def test_a_responsible_person_outside_the_space_gets_it_redacted(
    bench: Bench, make_space: MakeSpace
) -> None:
    _, run_id = await read_run(bench, make_space)
    await make_responsible(bench, "bob")
    r = await bench.people.bob.get(f"/api/runs/{run_id}/events")
    assert r.status_code == 200
    assert SECRET not in r.text and ANSWER not in r.text and "Read the plan" not in r.text
    items = r.json()["items"]
    tool = of_kind(items, "tool_call")[0]
    assert tool["redacted"] is True
    assert tool["content"]["name"] == "read_page" and tool["content"]["source"] == "wiki"
    assert "text" not in tool["content"] and "args" not in tool["content"]
    model = of_kind(items, "model_call")
    assert all(e["redacted"] for e in model)
    assert model[0]["content"]["tool_calls"][0]["name"] == "read_page"
    assert "args" not in model[0]["content"]["tool_calls"][0]
    assert model[0]["content"]["tokens_in"] > 0  # usage stays
    stop = of_kind(items, "stop")[0]
    assert stop["redacted"] is False and stop["content"]["reason"] == "completed"


async def test_a_responsible_person_in_the_space_reads_the_result(
    bench: Bench, make_space: MakeSpace
) -> None:
    _, run_id = await read_run(bench, make_space, "bob")
    await make_responsible(bench, "bob")
    items = await events(bench, "bob", run_id)
    tool = of_kind(items, "tool_call")[0]
    assert tool["redacted"] is False and SECRET in tool["content"]["text"]
    assert "args" not in tool["content"]  # the model's words stay the conversation's
    assert all(e["redacted"] for e in of_kind(items, "model_call"))


async def test_an_admin_reads_by_admin_right_and_it_is_noted(
    bench: Bench, make_space: MakeSpace
) -> None:
    space, run_id = await read_run(bench, make_space)
    await make_responsible(bench, "bob")  # the admin reads by agent.manage only
    assert await admin_entries(bench, space) == 0
    items = await events(bench, "admin", run_id)
    tool = of_kind(items, "tool_call")[0]
    assert tool["redacted"] is False and SECRET in tool["content"]["text"]
    assert await admin_entries(bench, space) == 1  # as for `GET /api/pages/{id}`
    assert all(e["redacted"] for e in of_kind(items, "model_call"))
    await events(bench, "admin", run_id)
    assert await admin_entries(bench, space) == 1  # once per admin, space and day


async def test_a_result_from_two_spaces_needs_both(bench: Bench, make_space: MakeSpace) -> None:
    users = bench.people.users
    alice = bench.people.alice
    both = [(users["alice"], SpaceRole.EDITOR), (users["bob"], SpaceRole.VIEWER)]
    shared = await make_space(SpaceKind.TEAM, members=both)
    closed = await make_space(SpaceKind.TEAM, members=[(users["alice"], SpaceRole.EDITOR)])
    for space in (shared, closed):
        await bench.join(space)
        await publish(alice, await new_page(alice, space.id, f"Zebra {space.id}", content_md="z"))
    bench.stub.state.replies.extend([call("search", query="Zebra"), {"content": ANSWER}])
    posted = await bench.say("Find Zebra")
    assert await bench.run_next() == StopReason.COMPLETED
    await make_responsible(bench, "bob")
    items = await events(bench, "bob", str(posted["agent_run"]["id"]))
    tool = of_kind(items, "tool_call")[0]
    assert tool["redacted"] is True and str(closed.id) not in str(items)


async def test_an_event_without_its_spaces_is_redacted_for_others(
    bench: Bench, make_space: MakeSpace
) -> None:
    """Events written before the spaces were noted show their result to the asker
    only."""
    _, run_id = await read_run(bench, make_space, "bob")
    tool = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == "tool_call"))
    assert tool is not None
    tool.content = {k: v for k, v in tool.content.items() if k != "spaces"}
    await bench.session.flush()
    await make_responsible(bench, "bob")
    assert of_kind(await events(bench, "bob", run_id), "tool_call")[0]["redacted"] is True
    assert of_kind(await events(bench, "alice", run_id), "tool_call")[0]["redacted"] is False

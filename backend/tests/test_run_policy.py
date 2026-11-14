"""Review Focus 1 (acceptance 14/M5): content of a `restricted` space never reaches an
`external` connection, by any tool, title or snippet; the stub logs every request and
the tests search the log for a secret word from the space. `none` spaces and pages
locked for AI are not there for a tool at all. The policy is read again before every
model call, so a change during a run counts."""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from sqlalchemy import func, select, update

from app.core.permissions import SpaceRole
from app.modules.agents.models import EventKind, RunEvent, StopReason
from app.modules.ai.models import AiPolicy
from app.modules.spaces.models import Space, SpaceKind
from app.modules.tickets.models import WorkItem
from app.modules.wiki.models import Page
from app.runtime.models import wrap_model
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket
from tests.factories_wiki import new_page, publish

SECRET = "Okapi77"


def call(name: str, **arguments: Any) -> dict[str, Any]:
    return {"tool_calls": [{"name": name, "arguments": arguments}]}


async def space_with_page(
    bench: Bench,
    make_space: MakeSpace,
    policy: AiPolicy,
    locations: list[str] | None = None,
    *,
    title: str = "Projekt Zebra",
    body: str = f"Das Kennwort lautet {SECRET}.",
) -> tuple[Space, dict[str, Any]]:
    alice = bench.people.users["alice"]
    space = await make_space(SpaceKind.TEAM, members=[(alice, SpaceRole.EDITOR)])
    await bench.join(space)
    page = await publish(
        bench.people.alice, await new_page(bench.people.alice, space.id, title, content_md=body)
    )
    space.ai_policy = policy
    space.allowed_locations = locations or []
    await bench.session.flush()
    return space, page


def sent(bench: Bench) -> str:
    return bench.stub.state.texts()


async def test_search_never_shows_a_restricted_space(bench: Bench, make_space: MakeSpace) -> None:
    await space_with_page(bench, make_space, AiPolicy.RESTRICTED, ["eu"], title=f"Zebra {SECRET}")
    await space_with_page(bench, make_space, AiPolicy.ANY, title="Zebra open", body="Nothing here.")
    bench.stub.state.replies.extend([call("search", query="Zebra"), {"content": "Done."}])
    await bench.say("Find Zebra")
    assert await bench.run_next() == StopReason.COMPLETED
    assert "Zebra open" in sent(bench)  # the search works
    assert SECRET not in sent(bench)  # neither title nor snippet of the restricted page


async def test_reading_a_restricted_page_stops_before_sending(
    bench: Bench, make_space: MakeSpace
) -> None:
    _, page = await space_with_page(bench, make_space, AiPolicy.RESTRICTED, ["eu", "local"])
    bench.stub.state.replies.extend([call("read_page", page_id=page["id"]), {"content": "leak"}])
    await bench.say("Read it")
    assert await bench.run_next() == StopReason.POLICY_BLOCKED
    assert len(bench.stub.state.log) == 1 and SECRET not in sent(bench)
    tool = await bench.session.scalar(select(RunEvent).where(RunEvent.kind == EventKind.TOOL_CALL))
    assert tool is not None and SECRET in tool.content["text"]  # kept in full in the run
    notice = [m for m in await bench.messages() if m["kind"] == "system"]
    assert notice[0]["system"]["new"]["value"] == "policy_blocked"


async def test_reading_a_restricted_ticket_stops_before_sending(
    bench: Bench, make_space: MakeSpace
) -> None:
    space, _ = await space_with_page(bench, make_space, AiPolicy.ANY, body="-")
    ticket = await new_ticket(bench.people.alice, space.id, "Zebra", description_md=SECRET)
    space.ai_policy, space.allowed_locations = AiPolicy.RESTRICTED, ["local"]
    await bench.session.flush()
    key = f"HC-{ticket['number']}"
    bench.stub.state.replies.extend([call("read_ticket", key=key), {"content": "leak"}])
    await bench.say("Read the ticket")
    assert await bench.run_next() == StopReason.POLICY_BLOCKED
    assert len(bench.stub.state.log) == 1 and SECRET not in sent(bench)


async def test_a_connection_the_policy_allows_gets_the_content(
    bench: Bench, make_space: MakeSpace
) -> None:
    await bench.locate("eu")
    _, page = await space_with_page(bench, make_space, AiPolicy.RESTRICTED, ["eu"])
    bench.stub.state.replies.extend([call("read_page", page_id=page["id"]), {"content": "ok"}])
    await bench.say("Read it")
    assert await bench.run_next() == StopReason.COMPLETED
    assert SECRET in sent(bench)
    assert '<untrusted source=\\"wiki\\"' in sent(bench)  # framed (JSON-escaped in the log)


@pytest.mark.parametrize("lock", ["none", "no_ai"])
async def test_none_spaces_and_locked_pages_are_not_there(
    bench: Bench, make_space: MakeSpace, lock: str
) -> None:
    await bench.locate("local")
    policy = AiPolicy.NONE if lock == "none" else AiPolicy.ANY
    _, page = await space_with_page(bench, make_space, policy, title=f"Zebra {SECRET}")
    if lock == "no_ai":
        row = await bench.session.get(Page, page["id"])
        assert row is not None
        row.no_ai = True
        await bench.session.flush()
    bench.stub.state.replies.extend(
        [
            call("search", query="Zebra"),
            call("read_page", page_id=page["id"]),
            {"content": "Nothing."},
        ]
    )
    await bench.say("Look")
    assert await bench.run_next() == StopReason.COMPLETED
    assert SECRET not in sent(bench)
    assert "Nothing found" in sent(bench)


async def test_a_policy_changed_during_the_run_counts(bench: Bench, make_space: MakeSpace) -> None:
    """The page is read under `any` and sent with the second call; during that call the
    space becomes `restricted`, so the third call never goes out."""
    space, page = await space_with_page(bench, make_space, AiPolicy.ANY)
    calls: list[str] = []

    async def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(str(messages[-1]))
        if len(calls) == 1:
            part = ToolCallPart("read_page", {"page_id": page["id"]}, tool_call_id="c1")
            return ModelResponse(parts=[part])
        if len(calls) == 2:
            space.ai_policy, space.allowed_locations = AiPolicy.RESTRICTED, ["local"]
            await bench.session.flush()
            return ModelResponse(parts=[ToolCallPart("search", {"query": "x"}, tool_call_id="c2")])
        return ModelResponse(parts=[TextPart("late")])

    executor = bench.executor(make_model=lambda target, timeout: wrap_model(FunctionModel(model)))
    await bench.say("Read it")
    assert await bench.run_next(executor) == StopReason.POLICY_BLOCKED
    assert len(calls) == 2 and SECRET in calls[1]


async def _moved_during_run(
    bench: Bench, first: ToolCallPart, change: Callable[[], Awaitable[None]]
) -> tuple[StopReason | None, list[str]]:
    """Read with `first`, then `change` while the model "thinks" about the next step;
    returns the stop and what each call sent (finding 3)."""
    calls: list[str] = []

    async def model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(str(messages))
        if len(calls) == 1:
            return ModelResponse(parts=[first])
        if len(calls) == 2:
            await change()
            return ModelResponse(parts=[ToolCallPart("search", {"query": "x"}, tool_call_id="c2")])
        return ModelResponse(parts=[TextPart("sent again")])

    executor = bench.executor(make_model=lambda target, timeout: wrap_model(FunctionModel(model)))
    await bench.say("Read it")
    return await bench.run_next(executor), calls


@pytest.mark.parametrize("where", ["none", "unreadable", "trash"])
async def test_a_page_moved_after_it_was_read_counts_where_it_is_now(
    bench: Bench, make_space: MakeSpace, where: str
) -> None:
    _, page = await space_with_page(bench, make_space, AiPolicy.ANY)
    if where == "none":
        target, _ = await space_with_page(bench, make_space, AiPolicy.NONE, title="Other")
    else:  # a space the agent is no member of
        target = await make_space(SpaceKind.TEAM, members=[(bench.people.users["alice"], "editor")])

    async def change() -> None:
        values = {"trashed_at": func.now()} if where == "trash" else {"space_id": target.id}
        await bench.session.execute(update(Page).where(Page.id == page["id"]).values(**values))

    first = ToolCallPart("read_page", {"page_id": page["id"]}, tool_call_id="c1")
    reason, calls = await _moved_during_run(bench, first, change)
    expected = StopReason.RIGHTS_REVOKED if where == "unreadable" else StopReason.POLICY_BLOCKED
    assert reason == expected
    assert len(calls) == 2  # the third call, with the page's text again, never went out


async def test_a_ticket_moved_after_it_was_read_counts_where_it_is_now(
    bench: Bench, make_space: MakeSpace
) -> None:
    space, _ = await space_with_page(bench, make_space, AiPolicy.ANY, body="-")
    target, _ = await space_with_page(bench, make_space, AiPolicy.ANY, title="Other")
    there = await new_ticket(bench.people.alice, target.id, "There")
    target.ai_policy = AiPolicy.NONE
    ticket = await new_ticket(bench.people.alice, space.id, "Zebra", description_md=SECRET)

    async def change() -> None:
        values = {"space_id": target.id, "status_id": there["status"]["id"]}
        await bench.session.execute(
            update(WorkItem).where(WorkItem.id == ticket["id"]).values(**values)
        )

    first = ToolCallPart("read_ticket", {"key": f"HC-{ticket['number']}"}, tool_call_id="c1")
    reason, calls = await _moved_during_run(bench, first, change)
    assert reason == StopReason.POLICY_BLOCKED
    assert len(calls) == 2 and SECRET in calls[1]

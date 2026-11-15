"""Plan M6 task 4: the listing tools of level 1, `list_tree`, `list_versions` and
`search_tickets`. Each reads with the run's actor (the person's rights, held to the
agent and the place), leaves out what AI may not read (policy `none`, pages locked
for AI, and what the connection's location may not receive), answers whatever it may
not read like a free id, and names the spaces it read from (the event's `spaces`)."""

import uuid

import pytest
from pydantic import ValidationError

from app.core.permissions import SpaceRole
from app.modules.agents.run_models import StopReason
from app.modules.agents.toolbox import listing
from app.modules.agents.toolbox.base import NOT_FOUND
from app.modules.ai.models import AiPolicy
from app.modules.spaces.models import Space, SpaceKind
from app.modules.wiki.models import Page
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace
from tests.factories_tickets import new_ticket, patch, status_of
from tests.factories_tools import call, tool_context
from tests.factories_wiki import new_page, publish

SECRET = "Okapi77"


@pytest.fixture
async def spaces(bench: Bench, make_space: MakeSpace) -> dict[str, Space]:
    """`both`: Alice (editor) and the agent (editor); `viewer`: Alice editor, the agent
    viewer; `alice_only` and `agent_only`; `none`: both, AI policy `none`."""
    alice, admin = bench.people.users["alice"], bench.people.users["admin"]
    names = ("both", "viewer", "alice_only", "agent_only", "none")
    made: dict[str, Space] = {}
    for name in names:
        members = [(admin, SpaceRole.EDITOR)]
        if name != "agent_only":
            members.append((alice, SpaceRole.EDITOR))
        made[name] = await make_space(SpaceKind.TEAM, name=f"Space {name}", members=members)
        if name != "alice_only":
            role = SpaceRole.VIEWER if name == "viewer" else SpaceRole.EDITOR
            await bench.join(made[name], role)
    made["none"].ai_policy = AiPolicy.NONE
    await bench.locate("local")
    return made


async def page(bench: Bench, space: Space, title: str, *, draft: bool = False, **kw: object) -> str:
    admin = bench.people.admin
    made = await new_page(admin, space.id, title, content_md=SECRET, **kw)  # type: ignore[arg-type]
    if not draft:
        made = await publish(admin, made)
    return str(made["id"])


# --- list_tree -------------------------------------------------------------------------


async def test_without_a_space_it_lists_the_spaces_both_may_read(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    ctx = await tool_context(bench)
    result = await listing.list_tree(ctx, listing.ListTreeArgs())
    for name in ("both", "viewer"):
        assert f"id={spaces[name].id}" in result.text
    for name in ("alice_only", "agent_only", "none"):
        assert str(spaces[name].id) not in result.text
    assert result.spaces == frozenset()  # names of spaces only: nothing read from them
    assert ctx.reads.spaces == set()


async def test_a_space_lists_its_pages_by_path_without_locked_ones(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    space = spaces["both"]
    parent = await page(bench, space, "Handbook")
    await page(bench, space, "Onboarding", parent_id=parent)
    locked = await page(bench, space, "Salaries")
    row = await bench.session.get(Page, uuid.UUID(locked))
    assert row is not None
    row.no_ai = True
    await bench.session.flush()
    ctx = await tool_context(bench)
    result = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=space.id))
    assert "handbook" in result.text and "handbook/onboarding" in result.text
    assert f"id={parent}" in result.text
    assert "Salaries" not in result.text and locked not in result.text
    assert SECRET not in result.text  # titles and paths, never content
    assert result.spaces == frozenset({space.id})
    assert ctx.reads.spaces == {space.id}


async def test_drafts_only_where_the_run_may_edit(bench: Bench, spaces: dict[str, Space]) -> None:
    for name in ("both", "viewer"):
        await page(bench, spaces[name], f"Draft {name}", draft=True)
    ctx = await tool_context(bench)
    shown = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=spaces["both"].id))
    assert "Draft both" in shown.text
    hidden = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=spaces["viewer"].id))
    assert "Draft viewer" not in hidden.text  # the agent only views there


@pytest.mark.parametrize("name", ["alice_only", "agent_only", "none", "unknown"])
async def test_a_space_it_may_not_read_is_not_there(
    bench: Bench, spaces: dict[str, Space], name: str
) -> None:
    if name != "unknown":
        await page(bench, spaces[name], f"Zebra {name}")
    space_id = spaces[name].id if name != "unknown" else uuid.uuid4()
    ctx = await tool_context(bench)
    result = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=space_id))
    assert result.text == NOT_FOUND
    assert result.spaces == frozenset() and ctx.reads.spaces == set()


async def test_a_restricted_space_its_location_may_not_receive_is_not_there(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    space = spaces["both"]
    await page(bench, space, "Zebra")
    space.ai_policy, space.allowed_locations = AiPolicy.RESTRICTED, ["eu"]
    await bench.session.flush()
    ctx = await tool_context(bench)
    assert (await listing.list_tree(ctx, listing.ListTreeArgs(space_id=space.id))).text == NOT_FOUND
    assert str(space.id) not in (await listing.list_tree(ctx, listing.ListTreeArgs())).text


async def test_a_long_tree_comes_in_pages(
    bench: Bench, spaces: dict[str, Space], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(listing, "TREE_PAGES", 2)
    space = spaces["both"]
    for title in ("Alpha", "Beta", "Gamma"):
        await page(bench, space, title)
    ctx = await tool_context(bench)
    first = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=space.id))
    assert "Alpha" in first.text and "Gamma" not in first.text
    cursor = first.attrs["next_cursor"]
    rest = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=space.id, cursor=cursor))
    assert "Gamma" in rest.text and "Alpha" not in rest.text and "next_cursor" not in rest.attrs
    bad = await listing.list_tree(ctx, listing.ListTreeArgs(space_id=space.id, cursor="x"))
    assert bad.text == "Invalid cursor."


# --- list_versions ---------------------------------------------------------------------


async def test_versions_list_numbers_and_authors_never_content(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    page_id = await page(bench, spaces["both"], "Plan")
    admin = bench.people.admin
    current = (await admin.get(f"/api/pages/{page_id}")).json()
    r = await admin.patch(
        f"/api/pages/{page_id}",
        json={"content_md": "Second", "change_summary": "Tidy", "version": current["version"]},
    )
    assert r.status_code == 200, r.text
    ctx = await tool_context(bench)
    result = await listing.list_versions(ctx, listing.ListVersionsArgs(page_id=uuid.UUID(page_id)))
    assert "version 2" in result.text and "version 1" in result.text
    assert result.text.index("version 2") < result.text.index("version 1")  # newest first
    assert "Tidy" in result.text
    assert SECRET not in result.text and "Second" not in result.text
    assert result.spaces == frozenset({spaces["both"].id})
    assert ctx.reads.spaces == {spaces["both"].id} and ctx.reads.pages == {uuid.UUID(page_id)}


@pytest.mark.parametrize("name", ["viewer", "alice_only", "none", "locked", "unknown"])
async def test_versions_need_the_right_to_edit_and_ai_access(
    bench: Bench, spaces: dict[str, Space], name: str
) -> None:
    if name == "unknown":
        page_id = str(uuid.uuid4())
    else:
        page_id = await page(bench, spaces["both" if name == "locked" else name], "Plan")
    if name == "locked":
        row = await bench.session.get(Page, uuid.UUID(page_id))
        assert row is not None
        row.no_ai = True
        await bench.session.flush()
    ctx = await tool_context(bench)
    args = listing.ListVersionsArgs(page_id=uuid.UUID(page_id))
    result = await listing.list_versions(ctx, args)
    assert result.text == NOT_FOUND
    assert result.spaces == frozenset() and ctx.reads.spaces == set()


# --- search_tickets --------------------------------------------------------------------


async def test_search_tickets_finds_only_where_the_run_may_read(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    admin = bench.people.admin
    for name in ("both", "alice_only", "agent_only", "none"):
        await new_ticket(admin, spaces[name].id, f"Zebra {name}")
    ctx = await tool_context(bench)
    result = await listing.search_tickets(ctx, listing.SearchTicketsArgs(query="Zebra"))
    assert "Zebra both" in result.text
    for name in ("alice_only", "agent_only", "none"):
        assert f"Zebra {name}" not in result.text
    assert result.spaces == frozenset({spaces["both"].id})
    assert ctx.reads.spaces == {spaces["both"].id} and len(ctx.reads.tickets) == 1


async def test_search_tickets_filters(bench: Bench, spaces: dict[str, Space]) -> None:
    admin, alice = bench.people.admin, bench.people.users["alice"]
    space = spaces["both"]
    mine = await new_ticket(admin, space.id, "Mine", assignee={"type": "user", "id": str(alice.id)})
    await new_ticket(admin, space.id, "Nobody's")
    done = await new_ticket(admin, space.id, "Finished", kind="bug")
    closed = await status_of(admin, space.id, "done")
    assert (await patch(admin, done, status_id=closed["id"])).status_code == 200
    ctx = await tool_context(bench)

    async def titles(**filters: object) -> str:
        args = listing.SearchTicketsArgs.model_validate(filters)
        return (await listing.search_tickets(ctx, args)).text

    assert "Mine" in await titles(assigned_to_me=True)
    assert "Nobody's" not in await titles(assigned_to_me=True)
    assert "Mine" not in await titles(unassigned=True)
    assert "Nobody's" in await titles(unassigned=True)
    assert "Finished" in await titles(status=["done"])
    assert "Mine" not in await titles(status=["done"])
    assert "Finished" in await titles(kind="bug") and "Mine" not in await titles(kind="bug")
    assert "Mine" in await titles(space_id=str(space.id))
    assert await titles(space_id=str(spaces["alice_only"].id)) == NOT_FOUND
    assert mine["number"]


async def test_search_tickets_leaves_out_what_the_location_may_not_receive(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    space = spaces["both"]
    await new_ticket(bench.people.admin, space.id, "Zebra restricted")
    space.ai_policy, space.allowed_locations = AiPolicy.RESTRICTED, ["eu"]
    await bench.session.flush()
    ctx = await tool_context(bench)
    result = await listing.search_tickets(ctx, listing.SearchTicketsArgs(query="Zebra"))
    assert result.text == NOT_FOUND


def test_arguments_are_checked() -> None:
    with pytest.raises(ValidationError):
        listing.SearchTicketsArgs.model_validate({"status": ["nonsense"]})
    with pytest.raises(ValidationError):
        listing.SearchTicketsArgs.model_validate({"assigned_to_me": True, "unassigned": True})
    with pytest.raises(ValidationError):
        listing.ListTreeArgs.model_validate({"space_id": "x"})
    with pytest.raises(ValidationError):
        listing.ListVersionsArgs.model_validate({"page_id": str(uuid.uuid4()), "extra": 1})


async def test_the_listing_tools_in_a_run_are_framed(
    bench: Bench, spaces: dict[str, Space]
) -> None:
    space = spaces["both"]
    page_id = await page(bench, space, "Zebra plan")
    await new_ticket(bench.people.admin, space.id, "Zebra ticket")
    bench.stub.state.replies.extend(
        [
            call("list_tree", space_id=str(space.id)),
            call("list_versions", page_id=page_id),
            call("search_tickets", query="Zebra"),
            {"content": "Done."},
        ]
    )
    await bench.say("Look around")
    assert await bench.run_next() == StopReason.COMPLETED
    sent = bench.stub.state.texts()
    assert sent.count("<untrusted") >= 3
    assert "Zebra plan" in sent and "Zebra ticket" in sent and "version 1" in sent

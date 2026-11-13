"""The ticket hierarchy (plan M4 decision 5): an epic has no parent; a story may have
an epic; a task or a bug an epic or a story; parent and child in the same space. So
the depth is at most three and a cycle cannot happen."""

from typing import Any

import pytest
from uuid_utils.compat import uuid7

from tests.factories_spaces import MakeSpace
from tests.factories_tickets import Desk, new_ticket, patch, status_of


async def _make(desk: Desk, kind: str, parent: dict[str, Any] | None = None) -> Any:
    body: dict[str, Any] = {"title": kind, "kind": kind}
    if parent is not None:
        body["parent_id"] = parent["id"]
    return await desk.editor.post(f"/api/spaces/{desk.space_id}/tickets", json=body)


@pytest.mark.parametrize(
    ("child", "parent", "allowed"),
    [
        ("story", "epic", True),
        ("task", "epic", True),
        ("bug", "epic", True),
        ("task", "story", True),
        ("bug", "story", True),
        ("epic", "epic", False),
        ("epic", "story", False),
        ("story", "story", False),
        ("story", "task", False),
        ("task", "task", False),
        ("task", "bug", False),
        ("bug", "bug", False),
    ],
)
async def test_which_kind_goes_under_which(
    desk: Desk, child: str, parent: str, allowed: bool
) -> None:
    above = (await _make(desk, parent)).json()
    r = await _make(desk, child, above)
    if allowed:
        assert r.status_code == 201, r.text
        assert r.json()["parent"] == {
            "id": above["id"],
            "number": above["number"],
            "key": above["key"],
            "title": parent,
            "kind": parent,
        }
    else:
        assert r.status_code == 422
        assert r.json()["error"]["code"] == "ticket.parent_invalid"


async def test_a_parent_of_another_space_or_none_at_all_is_the_same_422(
    desk: Desk, make_space: MakeSpace
) -> None:
    other = await make_space("team", "Geheim")  # the editor cannot see it
    hidden = await new_ticket(desk.admin, other.id, "Geheim", kind="epic")
    answers = []
    for parent_id in (hidden["id"], str(uuid7())):
        r = await desk.editor.post(
            f"/api/spaces/{desk.space_id}/tickets",
            json={"title": "X", "kind": "story", "parent_id": parent_id},
        )
        assert r.status_code == 422
        answers.append({k: v for k, v in r.json()["error"].items() if k != "trace_id"})
    assert answers[0] == answers[1]
    visible = await new_ticket(desk.admin, (await make_space("open", "Offen")).id, kind="epic")
    r = await desk.admin.post(
        f"/api/spaces/{desk.space_id}/tickets",
        json={"title": "X", "kind": "story", "parent_id": visible["id"]},
    )
    assert r.status_code == 422  # seen, but in another space
    assert r.json()["error"]["code"] == "ticket.parent_invalid"


async def test_a_ticket_is_not_its_own_parent(desk: Desk) -> None:
    story = await new_ticket(desk.editor, desk.space_id, kind="story")
    r = await patch(desk.editor, story, parent_id=story["id"])
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ticket.parent_invalid"


async def test_moving_under_another_parent_and_out(desk: Desk) -> None:
    epic_a = await new_ticket(desk.editor, desk.space_id, "A", kind="epic")
    epic_b = await new_ticket(desk.editor, desk.space_id, "B", kind="epic")
    story = (await _make(desk, "story", epic_a)).json()
    r = await patch(desk.editor, story, parent_id=epic_b["id"])
    assert r.json()["parent"]["id"] == epic_b["id"]
    r = await patch(desk.editor, r.json(), parent_id=None)
    assert r.status_code == 200
    assert r.json()["parent"] is None


async def test_a_kind_change_keeps_the_rules_for_parent_and_children(desk: Desk) -> None:
    epic = await new_ticket(desk.editor, desk.space_id, kind="epic")
    story = (await _make(desk, "story", epic)).json()
    task = (await _make(desk, "task", story)).json()
    r = await patch(desk.editor, epic, kind="story")  # its story child would sit below a story
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "ticket.kind_invalid"
    r = await patch(desk.editor, story, kind="task")  # it has a task child
    assert r.json()["error"]["code"] == "ticket.kind_invalid"
    r = await patch(desk.editor, task, kind="epic")  # an epic has no parent
    assert r.json()["error"]["code"] == "ticket.parent_invalid"
    r = await patch(desk.editor, task, kind="epic", parent_id=None)
    assert r.status_code == 200, r.text
    r = await patch(desk.editor, story, kind="bug")  # no children any more
    assert r.status_code == 200, r.text


async def test_children_are_counted_per_category(desk: Desk) -> None:
    epic = await new_ticket(desk.editor, desk.space_id, kind="epic")
    done = await status_of(desk.viewer, desk.space_id, "done")
    for status_id in (None, None, done["id"]):
        body: dict[str, Any] = {"title": "Kind", "kind": "story", "parent_id": epic["id"]}
        if status_id:
            body["status_id"] = status_id
        r = await desk.editor.post(f"/api/spaces/{desk.space_id}/tickets", json=body)
        assert r.status_code == 201
    children = (await desk.viewer.get(f"/api/tickets/{epic['number']}")).json()["children"]
    assert children == {"open": 2, "active": 0, "review": 0, "done": 1, "cancelled": 0}

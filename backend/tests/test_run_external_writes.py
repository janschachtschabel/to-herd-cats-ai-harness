"""Plan M8 decision 8: an external write tool acts outside. It is level 4, and every
call waits for the release of the person who asked, whatever the agent's entry says;
the release is bound to the arguments and to the server's and the tool's versions, so
a tool that changed since makes it stale. Nothing is sent before the release; a
rejection sends nothing."""

from typing import Any

from app.modules.agents.models import StopReason
from tests.factories_external import Ext, call
from tests.factories_mcp import SERVERS


async def asked(ext: Ext, **args: Any) -> dict[str, Any]:
    """A run that called `create_issue` and now waits for Alice's release."""
    await ext.level(4)
    await ext.grant(create_issue="allow")
    name = await ext.name("create_issue")
    ext.bench.stub.state.replies.extend([call(name, **args), {"content": "Angelegt."}])
    await ext.bench.say("Lege das Issue an")
    assert await ext.bench.run_next() is None  # waits
    r = await ext.bench.people.alice.get("/api/approvals", params={"state": "pending"})
    (approval,) = r.json()["items"]
    return dict(approval)


async def decide(ext: Ext, approval: dict[str, Any], decision: str, **more: Any) -> Any:
    body = {"decision": decision, "version": approval["version"], **more}
    return await ext.bench.people.alice.post(f"/api/approvals/{approval['id']}/decide", json=body)


async def test_a_write_tool_is_offered_from_level_four_and_waits_for_a_release(
    ext: Ext,
) -> None:
    approval = await asked(ext, title="Login kaputt")
    name = await ext.name("create_issue")
    assert name in ext.offered(0)
    assert "(acts outside; every call waits for the release" in ext.offered(0)[name]["description"]
    assert ext.stub.state.calls == []  # nothing sent yet
    assert approval["tool"] == name and approval["summary"] == "Tracker · create_issue"
    assert approval["args"] == {"title": "Login kaputt"}  # for Alice, who decides
    tool = (await ext.tools())["create_issue"]
    assert approval["external"] == {"server_id": ext.server["id"], "tool_id": tool["id"]}
    (card,) = [m for m in await ext.bench.messages() if m["kind"] == "approval"]
    assert card["body_md"] == "Tracker · create_issue" and "Login" not in card["body_md"]
    r = await decide(ext, approval, "approve")
    assert r.status_code == 200, r.text
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert ext.stub.state.calls == [("create_issue", {"title": "Login kaputt"})]
    shown = (await ext.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] == "ran"


async def test_an_entry_never_loosens_a_write_tool_below_a_release(ext: Ext) -> None:
    await ext.level(4)
    await ext.grant(create_issue="allow")
    grants = {t["name"]: t for t in (await ext.grants())["tools"]}
    entry = grants[await ext.name("create_issue")]
    assert (entry["level"], entry["entry"], entry["effective"]) == (4, "allow", "confirm")
    await ext.level(3)
    grants = {t["name"]: t for t in (await ext.grants())["tools"]}
    assert grants[await ext.name("create_issue")]["effective"] == "block"


async def test_others_see_no_arguments(ext: Ext) -> None:
    approval = await asked(ext, title="Geheim 42")
    admin = await ext.admin.get(f"/api/approvals/{approval['id']}")
    assert admin.status_code == 200
    assert admin.json()["args"] is None and admin.json()["redacted"] is True
    r = await ext.admin.post(
        f"/api/approvals/{approval['id']}/decide",
        json={"decision": "approve", "version": approval["version"]},
    )
    assert r.status_code == 403 and r.json()["error"]["code"] == "approval.not_addressed"


async def test_a_rejection_sends_nothing(ext: Ext) -> None:
    approval = await asked(ext, title="Nein")
    r = await decide(ext, approval, "reject", reason="Nicht jetzt")
    assert r.status_code == 200, r.text
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert ext.stub.state.calls == []
    result = (await ext.tool_events())[-1]
    assert result["text"].startswith("approval_rejected:") and "Nicht jetzt" in result["text"]


async def test_a_tool_changed_since_the_release_makes_it_stale(ext: Ext) -> None:
    """The server described the tool otherwise and an admin approved that: the release
    was given for the tool as it was, so nothing is sent."""
    approval = await asked(ext, title="Alt")
    ext.stub.state.tools[1]["description"] = "Create an issue, now with labels."
    r = await ext.admin.post(f"{SERVERS}/{ext.server['id']}/refresh", json={})
    assert r.json()["changed"] == 1
    tool = (await ext.tools())["create_issue"]
    r = await ext.admin.post(
        f"{SERVERS}/{ext.server['id']}/tools/{tool['id']}/approve",
        json={"version": tool["version"]},
    )
    assert r.status_code == 200, r.text
    r = await decide(ext, approval, "approve")
    assert r.status_code == 200, r.text
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert ext.stub.state.calls == []
    assert (await ext.tool_events())[-1]["text"].startswith("approval_stale:")
    shown = (await ext.bench.people.alice.get(f"/api/approvals/{approval['id']}")).json()
    assert shown["outcome"] == "stale"


async def test_a_server_moved_since_the_release_is_not_called(ext: Ext) -> None:
    approval = await asked(ext, title="Alt")
    await ext.patch_server(name="Tracker 2")  # any change of the server counts
    r = await decide(ext, approval, "approve")
    assert r.status_code == 200, r.text
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert ext.stub.state.calls == []
    assert (await ext.tool_events())[-1]["text"].startswith("approval_stale:")

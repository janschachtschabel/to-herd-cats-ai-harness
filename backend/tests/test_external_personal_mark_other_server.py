"""Module review M8 1, finding 3: the personal mark (`Reads.personal`) holds back every write inside the system,
but not a call of another external tool. A run that read through the asking person's
own connector may pass what it read on, as arguments, to a `read` tool of a server
that works with the organisation's shared connector: no release, no check. Now such a
call waits for the person's release of exactly those arguments; a call through the
person's own connector goes on without one."""

from typing import Any

from app.modules.agents.run_models import StopReason
from tests.factories_connectors import PERSONAL as MY_CONNECTORS
from tests.factories_connectors import make_connector
from tests.factories_external import Ext, call
from tests.factories_mcp import approve_as_listed, make_server

SECRET = "PRIVAT-Gnu-4"


async def _two_servers(ext: Ext) -> dict[str, str]:
    """`Tracker` takes Alice's own connector, `Teamtracker` none; the agent may call
    `search_issues` of both. The run names by server."""
    shared = await make_server(ext.admin, ext.stub, name="Teamtracker")
    await approve_as_listed(ext.admin, shared["id"])
    await ext.patch_server(connector_scope="personal")
    await make_connector(ext.bench.people.alice, MY_CONNECTORS, mcp_server_id=ext.server["id"])
    names: dict[str, str] = {}
    for entry in (await ext.grants())["tools"]:
        external = entry["external"] or {}
        if external.get("tool_name") == "search_issues":
            names[external["server_name"]] = entry["name"]
    version = (await ext.grants())["version"]
    tools = [{"tool": name, "policy": "allow"} for name in names.values()]
    r = await ext.admin.put(f"{ext.agent_url}/tools", json={"tools": tools, "version": version})
    assert r.status_code == 200, r.text
    ext.stub.state.results["search_issues"] = {"text": SECRET}
    return names


async def _pending(ext: Ext) -> list[dict[str, Any]]:
    r = await ext.bench.people.alice.get("/api/approvals", params={"state": "pending"})
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


async def test_a_personal_result_is_not_sent_on_to_a_shared_server(ext: Ext) -> None:
    """A correct system lets nothing read through the person's own connector leave to
    anyone but that person without their say: a call to a server with shared access
    is refused (or waits for the person's release) once the run carries the mark."""
    names = await _two_servers(ext)
    ext.bench.stub.state.replies.extend(
        [
            call(names["Tracker"], q="meine"),
            call(names["Teamtracker"], q=f"weitergereicht: {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Such meine Issues")
    await ext.bench.run_next()
    sent = [arguments for _, arguments in ext.stub.state.calls]
    assert sent[0] == {"q": "meine"}
    assert not any(SECRET in str(arguments) for arguments in sent[1:]), sent


async def test_the_person_releases_exactly_what_goes_on_to_another_server(ext: Ext) -> None:
    """The call waits for Alice's release, which shows her the exact arguments; once
    she releases it, it is sent as shown."""
    names = await _two_servers(ext)
    onward = {"q": f"weitergereicht: {SECRET}"}
    ext.bench.stub.state.replies.extend(
        [call(names["Tracker"], q="meine"), call(names["Teamtracker"], **onward)]
    )
    ext.bench.stub.state.replies.append({"content": "Erledigt."})
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() is None  # waits for Alice
    (approval,) = await _pending(ext)
    assert approval["tool"] == names["Teamtracker"] and approval["args"] == onward
    assert approval["personal"] is True  # its card says why (module review M8 2)
    body = {"decision": "approve", "version": approval["version"]}
    r = await ext.bench.people.alice.post(f"/api/approvals/{approval['id']}/decide", json=body)
    assert r.status_code == 200, r.text
    await ext.bench.run_next()
    assert [arguments for _, arguments in ext.stub.state.calls] == [{"q": "meine"}, onward]


async def test_the_persons_own_connector_needs_no_release_after_the_mark(ext: Ext) -> None:
    """A second call through Alice's own connector stays with her: no release."""
    names = await _two_servers(ext)
    ext.bench.stub.state.replies.extend(
        [
            call(names["Tracker"], q="meine"),
            call(names["Tracker"], q=f"mehr zu {SECRET}"),
            {"content": "Erledigt."},
        ]
    )
    await ext.bench.say("Such meine Issues")
    assert await ext.bench.run_next() == StopReason.COMPLETED
    assert len(ext.stub.state.calls) == 2 and await _pending(ext) == []

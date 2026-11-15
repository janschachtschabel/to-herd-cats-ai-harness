"""Helpers for the personal mark's tests (module review M8 2): a run under the mark
that wants to write where others read waits for the asking person's release."""

from typing import Any

from httpx import AsyncClient

from tests.factories_external import Ext


async def pending(client: AsyncClient) -> list[dict[str, Any]]:
    r = await client.get("/api/approvals", params={"state": "pending"})
    assert r.status_code == 200, r.text
    return list(r.json()["items"])


async def asks_release(ext: Ext, run_result: object, who: str = "alice") -> dict[str, Any]:
    """The run waits (`run_next` gave None) for one personal release, addressed to
    `who`, which shows her exactly what would be written."""
    assert run_result is None, run_result
    (approval,) = await pending(getattr(ext.bench.people, who))
    assert approval["personal"] is True and approval["args"] is not None
    return approval


async def decide(ext: Ext, approval: dict[str, Any], decision: str, who: str = "alice") -> None:
    body = {"decision": decision, "version": approval["version"]}
    r = await getattr(ext.bench.people, who).post(
        f"/api/approvals/{approval['id']}/decide", json=body
    )
    assert r.status_code == 200, r.text

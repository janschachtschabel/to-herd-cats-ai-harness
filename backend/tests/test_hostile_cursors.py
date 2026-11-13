"""Every list endpoint answers 422 in the error shape for any cursor it cannot use.

The list endpoints are found in the OpenAPI document (every GET with a `cursor`
parameter), so a new list endpoint is covered without being added here.
"""

import base64
import json

import pytest
from httpx import AsyncClient

from app.modules.groups.models import Group
from app.modules.users.models import User
from app.web.public import create_public_app

UUID = "0190f0f0-0000-7000-8000-000000000000"


def _b64(raw: bytes | str) -> str:
    data = raw.encode("utf-8", "surrogatepass") if isinstance(raw, str) else raw
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


HOSTILE: dict[str, str] = {
    "lone_surrogate_key": _b64(json.dumps(["a\ud800b", UUID])),
    "lone_surrogate_raw": _b64(f"2026-01-01T00:00:00+00:00\ud800|{UUID}"),
    "timestamp_overflow_high": _b64(f"9999-12-31T23:59:59-23:59|{UUID}"),
    "timestamp_overflow_low": _b64(f"0001-01-01T00:00:00+23:59|{UUID}"),
    "timestamp_naive": _b64(f"2026-01-01T00:00:00|{UUID}"),
    "key_wrong_types": _b64(json.dumps([1, 2])),
    "key_uuid_as_number": _b64(json.dumps(["a", 5])),
    "key_object": _b64(json.dumps({"a": 1, "b": 22})),
    "key_nulls": _b64(json.dumps([None, None])),
    "key_nested": _b64(json.dumps([["a"], UUID])),
    "key_with_nul": _b64(json.dumps(["a\x00", UUID])),
    "huge_integer": _b64("9" * 5000),
    "huge_float": _b64(json.dumps([1e308, UUID]).replace("1e+308", "1e999")),
    "deep_nesting": _b64("[" * 5_000),
    "truncated_base64": "QUJDRE",
    "bad_base64_length": "AAAAA",
    "not_base64": "!!!",
    "non_ascii": "äöü",
    "invalid_utf8": _b64(b"\xff\xfe\xfd|x"),
    "short_id": _b64(b"\x01\x02\x03"),
    "empty": "",
}


def _list_endpoints() -> list[str]:
    paths = create_public_app().openapi()["paths"]
    return sorted(
        path
        for path, operations in paths.items()
        if any(p["name"] == "cursor" for p in operations.get("get", {}).get("parameters", []))
    )


def test_the_list_endpoints_are_found() -> None:
    endpoints = _list_endpoints()
    assert len(endpoints) >= 11
    assert {
        "/api/channels",
        "/api/spaces/{space_id}/channels",
        "/api/conversations/{conversation_id}/messages",
        "/api/messages/{message_id}/replies",
        "/api/dms",
        "/api/conversations/unread",
        "/api/activity",
        "/api/admin/dm-inspect",
        "/api/admin/dm-inspect/{inspection_id}/messages",
    } <= set(endpoints)


@pytest.mark.parametrize("name", sorted(HOSTILE))
async def test_hostile_cursors_answer_422_everywhere(
    name: str, owner: AsyncClient, group: Group, member: User
) -> None:
    space_id = (await owner.post("/api/spaces", json={"kind": "team", "name": "T"})).json()["id"]
    page = await owner.post(f"/api/spaces/{space_id}/pages", json={"title": "Seite"})
    channel = await owner.post(f"/api/spaces/{space_id}/channels", json={"name": "k"})
    message = await owner.post(
        f"/api/conversations/{channel.json()['id']}/messages", json={"body_md": "m"}
    )
    dm = await owner.post("/api/dms", json={"user_ids": [str(member.id)]})
    inspection = await owner.post(
        "/api/admin/dm-inspect",
        json={"conversation_id": dm.json()["id"], "reason": "hostile cursor test"},
    )
    ticket = await owner.post(f"/api/spaces/{space_id}/tickets", json={"title": "Ticket"})
    ids = {
        "{number}": str(ticket.json()["number"]),
        "{category}": "open",
        "{status_id}": ticket.json()["status"]["id"],
        "{inspection_id}": inspection.json()["id"],
        "{space_id}": space_id,
        "{group_id}": str(group.id),
        "{page_id}": page.json()["id"],
        "{conversation_id}": channel.json()["id"],
        "{message_id}": message.json()["id"],
    }
    for template in _list_endpoints():
        path = template
        for placeholder, value in ids.items():
            path = path.replace(placeholder, value)
        # Lists that need more than a cursor.
        extra = {"user_id": str(member.id)} if template == "/api/admin/dm-inspect" else {}
        response = await owner.get(path, params={"cursor": HOSTILE[name], **extra})
        if name == "empty":
            # An empty cursor means "first page".
            assert response.status_code == 200, (path, response.text)
            continue
        assert response.status_code == 422, (path, response.text)
        error = response.json()["error"]
        assert error["code"] == "validation_failed" and len(error["trace_id"]) == 32

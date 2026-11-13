"""The admin's inspection of direct messages (spec 5.5, plan decision 6, review focus
6): only with `dm.inspect`, a reason, for 60 minutes, recorded in the audit log, read
only, and visible to the participants. Without one an admin sees no DM of others."""

import uuid
from datetime import timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.modules.audit.models import AuditLog
from app.modules.messaging.models import DmInspection
from tests.factories import login
from tests.factories_dms import People, dm_of
from tests.factories_messaging import post, send

INSPECT = "/api/admin/dm-inspect"
REASON = "Hinweis auf Belästigung, Ticket 4711"


async def _grant(people: People, conversation_id: object, reason: str = REASON) -> dict:
    response = await people.admin.post(
        INSPECT, json={"conversation_id": str(conversation_id), "reason": reason}
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


async def test_find_lists_names_and_times_but_no_content(
    people: People, session: AsyncSession
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "streng vertraulich")
    await dm_of(people.bob, people.id("carol"))
    found = await people.admin.get(INSPECT, params={"user_id": people.id("alice")})
    assert found.status_code == 200, found.text
    items = found.json()["items"]
    assert [i["conversation_id"] for i in items] == [dm["id"]]
    assert {p["name"] for p in items[0]["participants"]} == {"Alice", "Bob"}
    assert items[0]["last_message_at"] == message["created_at"]
    assert "vertraulich" not in found.text
    looked_up = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "dm.admin_lookup"))
    ).all()
    assert [(a.actor_id, a.target_type, a.target_id) for a in looked_up] == [
        (people.users["admin"].id, "user", people.users["alice"].id)
    ]


async def test_a_reason_is_required(people: People) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    for body in (
        {"conversation_id": dm["id"]},
        {"conversation_id": dm["id"], "reason": ""},
        {"conversation_id": dm["id"], "reason": "zu kurz!!"},  # nine characters
        {"conversation_id": dm["id"], "reason": "   kurz          "},
        {"conversation_id": dm["id"], "reason": "x" * 501},
    ):
        response = await people.admin.post(INSPECT, json=body)
        assert response.status_code == 422, body


async def test_an_inspection_is_audited_and_reads_for_an_hour(
    people: People, session: AsyncSession
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "Hallo")
    reply = await post(people.bob, dm["id"], "Hi", parent_id=message["id"])
    inspection = await _grant(people, dm["id"])
    assert inspection["conversation_id"] == dm["id"] and inspection["reason"] == REASON
    granted = inspection["granted_at"]
    stored = await session.get(DmInspection, uuid.UUID(inspection["id"]))
    assert stored is not None
    assert stored.expires_at - stored.granted_at == timedelta(minutes=60)
    assert inspection["expires_at"].startswith(stored.expires_at.isoformat()[:19])
    audited = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "dm.admin_access"))
    ).all()
    assert [(a.actor_id, a.target_type, str(a.target_id)) for a in audited] == [
        (people.users["admin"].id, "conversation", dm["id"])
    ]
    assert audited[0].details == {"reason": REASON, "inspection_id": inspection["id"]}
    read = await people.admin.get(f"{INSPECT}/{inspection['id']}/messages")
    assert read.status_code == 200, read.text
    assert [m["id"] for m in read.json()["items"]] == [reply["id"], message["id"]]
    shown = (await people.bob.get(f"/api/conversations/{dm['id']}")).json()
    assert shown["inspections"] == [{"at": granted, "admin_name": "Admin"}]


async def test_an_inspection_ends_after_its_hour(people: People, session: AsyncSession) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    inspection = await _grant(people, dm["id"])
    await session.execute(
        update(DmInspection)
        .where(DmInspection.id == uuid.UUID(inspection["id"]))
        .values(
            granted_at=DmInspection.granted_at - timedelta(minutes=61),
            expires_at=DmInspection.expires_at - timedelta(minutes=61),
        )
    )
    response = await people.admin.get(f"{INSPECT}/{inspection['id']}/messages")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "dm_inspection.not_found"


async def test_an_inspection_is_its_admins_and_needs_the_right_still(
    people: People, make_user, make_client, session: AsyncSession
) -> None:
    dm = await dm_of(people.alice, people.id("bob"))
    inspection = await _grant(people, dm["id"])
    other = await make_user(SystemRole.ADMIN)
    other_client = await make_client(csrf=True)
    await login(other_client, other.email)
    path = f"{INSPECT}/{inspection['id']}/messages"
    assert (await other_client.get(path)).status_code == 404
    assert (await other_client.get(f"{INSPECT}/{uuid.uuid4()}/messages")).status_code == 404
    people.users["admin"].system_role = SystemRole.MEMBER
    await session.flush()
    demoted = await people.admin.get(path)
    assert demoted.status_code == 403
    assert demoted.json()["error"]["code"] == "auth.permission_denied"


async def test_only_direct_messages_are_inspected(people: People, chat) -> None:
    for conversation_id in (chat.channel_id, uuid.uuid4()):
        response = await people.admin.post(
            INSPECT, json={"conversation_id": str(conversation_id), "reason": REASON}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "conversation.not_found"


async def test_an_inspection_opens_no_other_door(people: People) -> None:
    """Read only, through its own route: the conversation's routes stay closed."""
    dm = await dm_of(people.alice, people.id("bob"))
    message = await post(people.alice, dm["id"], "Hallo")
    await _grant(people, dm["id"])
    conversation = f"/api/conversations/{dm['id']}"
    for method, path, body, code in (
        ("GET", conversation, None, "conversation.not_found"),
        ("GET", f"{conversation}/messages", None, "conversation.not_found"),
        ("POST", f"{conversation}/messages", {"body_md": "x"}, "conversation.not_found"),
        ("GET", f"/api/messages/{message['id']}/replies", None, "message.not_found"),
        ("PATCH", f"/api/messages/{message['id']}", {"body_md": "x"}, "message.not_found"),
        ("DELETE", f"/api/messages/{message['id']}", None, "message.not_found"),
    ):
        response = await people.admin.request(method, path, json=body)
        assert response.status_code == 404, (method, path, response.text)
        assert response.json()["error"]["code"] == code
    reply = await send(people.admin, dm["id"], "x", parent_id=message["id"])
    assert reply.status_code == 404
    assert [d["id"] for d in (await people.admin.get("/api/dms")).json()["items"]] == []

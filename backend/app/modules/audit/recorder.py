"""Writing the audit log. Services call `record` in the transaction of their change,
after it, so a failed change leaves no entry and a recorded one cannot go missing.

Details name what changed, never secrets: no passwords, hashes or tokens.
"""

import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.request_context import client_ip
from app.modules.audit.models import (
    ADMIN_ACCESS,
    AGENT_ADMIN_ACCESS,
    CALENDAR_ADMIN_WRITE,
    CALENDAR_PRIVATE_READ,
    AuditLog,
)
from app.modules.audit.repository import AuditRepository


async def record(
    session: AsyncSession,
    actor: Actor,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    details: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        **_who(actor),
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
    )
    await AuditRepository(session).add(entry)


SYSTEM_ACTOR_TYPE = "system"
SYSTEM_ACTOR_ID = uuid.UUID(int=0)


async def record_system(
    session: AsyncSession,
    org_id: uuid.UUID,
    action: str,
    target_type: str,
    target_id: uuid.UUID,
    details: dict[str, Any] | None = None,
) -> None:
    """An entry of the installation itself (a backup from the command line or the
    scheduled job): actor `system`, no person, no address."""
    entry = AuditLog(
        org_id=org_id,
        actor_type=SYSTEM_ACTOR_TYPE,
        actor_id=SYSTEM_ACTOR_ID,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        ip=None,
    )
    await AuditRepository(session).add(entry)


async def record_admin_access(
    session: AsyncSession, actor: Actor, space_id: uuid.UUID, kind: str
) -> None:
    """An admin opened a team or personal space they are not a member of (spec 5.5):
    one entry per admin, space and UTC day."""
    await AuditRepository(session).add_unless_present(
        **_who(actor),
        action=ADMIN_ACCESS,
        target_type="space",
        target_id=space_id,
        details={"kind": kind},
    )


async def record_agent_admin_access(
    session: AsyncSession, actor: Actor, agent_ids: Iterable[uuid.UUID]
) -> None:
    """An admin was shown someone else's personal agents (plan M6 decision 13): one
    entry per admin, agent and UTC day, in one statement."""
    rows = [
        {
            **_who(actor),
            "action": AGENT_ADMIN_ACCESS,
            "target_type": "agent",
            "target_id": agent_id,
            "details": None,
        }
        for agent_id in sorted(set(agent_ids))
    ]
    await AuditRepository(session).add_many_unless_present(rows)


async def record_private_event_reads(
    session: AsyncSession, actor: Actor, events: Iterable[tuple[uuid.UUID, uuid.UUID, uuid.UUID]]
) -> None:
    """An admin read private calendar events by admin power alone (plan M10, review
    task 3a R3a-4): one entry per admin, event and UTC day, in one statement; `events`
    are (event, space, calendar) ids, the only details."""
    rows = [
        {
            **_who(actor),
            "action": CALENDAR_PRIVATE_READ,
            "target_type": "calendar_event",
            "target_id": event_id,
            "details": {"space_id": str(space_id), "calendar_id": str(calendar_id)},
        }
        for event_id, space_id, calendar_id in sorted(set(events))
    ]
    await AuditRepository(session).add_many_unless_present(rows)


async def record_event_admin_write(
    session: AsyncSession,
    actor: Actor,
    event: tuple[uuid.UUID, uuid.UUID, uuid.UUID],
    *,
    change: str,
    scope: str,
    fields: Iterable[str],
) -> None:
    """An admin changed or deleted a calendar event by admin power alone (plan M10,
    task 3b): one entry per write; `event` is (event, space, calendar) ids, the details
    name the change, its scope and the changed fields, never their values."""
    event_id, space_id, calendar_id = event
    await record(
        session,
        actor,
        CALENDAR_ADMIN_WRITE,
        "calendar_event",
        event_id,
        {
            "space_id": str(space_id),
            "calendar_id": str(calendar_id),
            "change": change,
            "scope": scope,
            "fields": sorted(fields),
        },
    )


def snapshot(entity: object, fields: Iterable[str]) -> dict[str, Any]:
    """The fields' values now, to compare with `changes` after an update."""
    return {name: getattr(entity, name) for name in fields}


def changes(before: dict[str, Any], entity: object) -> dict[str, dict[str, Any]]:
    """`{field: {"from": old, "to": new}}` for every field of `before` that changed."""
    return {
        name: {"from": old, "to": getattr(entity, name)}
        for name, old in before.items()
        if getattr(entity, name) != old
    }


def _who(actor: Actor) -> dict[str, Any]:
    return {
        "org_id": actor.org_id,
        "actor_type": actor.principal.type,
        "actor_id": actor.principal.id,
        "ip": client_ip(),
    }

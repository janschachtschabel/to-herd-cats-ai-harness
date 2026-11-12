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
from app.modules.audit.models import ADMIN_ACCESS, AuditLog
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

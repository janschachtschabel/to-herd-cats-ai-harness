from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page
from app.modules.audit.schemas import AuditOut, AuditQuery
from app.modules.audit.service import AuditService
from app.modules.auth.deps import ActorDep, SessionDep

router = APIRouter(prefix="/admin/audit", tags=["audit"])


@router.get("", response_model=Page[AuditOut])
async def list_audit(
    query: Annotated[AuditQuery, Query()], actor: ActorDep, session: SessionDep
) -> Page[AuditOut]:
    page = await AuditService(session).list(actor, query)
    return Page[AuditOut](
        items=[AuditOut.of(row) for row in page.items], next_cursor=page.next_cursor
    )

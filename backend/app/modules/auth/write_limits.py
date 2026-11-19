"""Which requests the write limit per person counts (J10, `core/write_limit.py`): every
unsafe method on the routers of content (pages, attachments, messages, tickets, skills,
calendars and what hangs on them), included with `COUNTED`, and single content routes of other
routers (`POST /api/spaces`, an automation's manual run, a question's answer) marked
with `COUNTED` at the route. Reading never counts, nor do read markers, the
administration, settings, AI configuration or the session's own touch.

A route whose writes are uploads (attachments, imports) carries `UPLOAD` besides: it
counts in the upload area instead. Both are decided at the route, never by its path;
`tests/test_write_limit_routes.py` demands a decision for every unsafe `/api` route."""

from fastapi import Depends, Request

from app.core.write_limit import Area, admit_now
from app.modules.auth.deps import UNSAFE_METHODS, AuthDep, SessionDep, SettingsDep


async def mark_upload() -> None:
    """Marks a route whose writes count as uploads; does nothing itself."""


def is_upload(route: object) -> bool:
    """Whether `route` (an `APIRoute`) carries the `UPLOAD` mark."""
    return any(
        getattr(dependency, "dependency", None) is mark_upload
        for dependency in getattr(route, "dependencies", ())
    )


async def count_write(
    request: Request, ctx: AuthDep, session: SessionDep, settings: SettingsDep
) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    area = Area.UPLOAD if is_upload(request.scope.get("route")) else Area.WRITE
    await admit_now(session, settings, ctx.principal, area)


COUNTED = [Depends(count_write)]
UPLOAD = [Depends(mark_upload)]

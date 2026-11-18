"""Which requests the write limit per person counts (J10, `core/write_limit.py`): every
unsafe method on the routers of content (pages, attachments, messages, tickets and
what hangs on them), included with `COUNTED`. Uploads (attachments, imports) count
in their own area; reading never counts, nor do read markers, the administration or
settings."""

import re

from fastapi import Depends, Request

from app.core.write_limit import Area, admit_now
from app.modules.auth.deps import UNSAFE_METHODS, AuthDep, SessionDep, SettingsDep

UPLOADS = (
    re.compile(r"/api/pages/[^/]+/attachments"),
    re.compile(r"/api/spaces/[^/]+/import"),
    re.compile(r"/api/skills/import"),
)


async def count_write(
    request: Request, ctx: AuthDep, session: SessionDep, settings: SettingsDep
) -> None:
    if request.method not in UNSAFE_METHODS:
        return
    path = request.url.path
    area = Area.UPLOAD if any(p.fullmatch(path) for p in UPLOADS) else Area.WRITE
    await admit_now(session, settings, ctx.principal, area)


COUNTED = [Depends(count_write)]

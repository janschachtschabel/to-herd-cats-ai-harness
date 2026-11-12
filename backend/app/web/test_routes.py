"""Routes that exist only when environment == "test"; they exercise the error handlers
and the log context."""

import logging
from typing import Any

from fastapi import APIRouter

from app.core.errors import NotFound
from app.modules.auth.deps import AuthDep

router = APIRouter(prefix="/_test")
logger = logging.getLogger("app.test_routes")


@router.get("/not-found")
async def not_found() -> None:
    raise NotFound("Nothing here", code="test.not_found")


@router.get("/boom")
async def boom() -> None:
    raise RuntimeError("boom")


@router.get("/needs-int")
async def needs_int(n: int) -> dict[str, int]:
    return {"n": n}


@router.get("/ok")
async def ok() -> dict[str, bool]:
    return {"ok": True}


@router.get("/items/{item_id}")
async def item(item_id: int) -> dict[str, int]:
    return {"item_id": item_id}


@router.post("/boom-post")
async def boom_post(payload: dict[str, Any]) -> None:
    # The body is accepted and ignored: it must never show up in the error log.
    raise RuntimeError("boom")


@router.get("/whoami")
async def whoami(ctx: AuthDep) -> dict[str, str]:
    logger.info("test.whoami")
    return {"actor": str(ctx.principal)}

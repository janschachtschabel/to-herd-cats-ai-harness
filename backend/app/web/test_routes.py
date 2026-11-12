"""Routes that exist only when environment == "test"; they exercise the error handlers."""

from typing import Any

from fastapi import APIRouter

from app.core.errors import NotFound

router = APIRouter(prefix="/_test")


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

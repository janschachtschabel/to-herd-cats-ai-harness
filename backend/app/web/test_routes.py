"""Routes that exist only when environment == "test"; they exercise the error handlers."""

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

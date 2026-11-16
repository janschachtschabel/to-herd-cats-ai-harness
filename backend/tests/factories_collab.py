"""The internal collab API under test: the internal app on the test session (with and
without the internal token) and helpers for its calls. `grant_of` issues a grant the
way the relay does (`CollabService.admit`)."""

import base64
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.modules.wiki.collab_service import CollabService
from app.web.internal import create_internal_app
from tests.app_session import session_override

TOKEN = "t" * 40
HEADER = "X-Herd-Internal-Token"


@pytest.fixture
def internal_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(get_settings(), "internal_token", SecretStr(TOKEN))
    return TOKEN


@pytest.fixture
async def internal(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """The internal app on the test session, without the token header."""
    app = create_internal_app()
    app.dependency_overrides[get_session] = session_override(session)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://internal") as client:
        yield client


@pytest.fixture
async def collab(internal: AsyncClient, internal_token: str) -> AsyncClient:
    internal.headers[HEADER] = internal_token
    return internal


def token_of(client: AsyncClient) -> str:
    token = client.cookies.get(get_settings().session_cookie_name)
    assert token
    return token


async def grant_of(
    session: AsyncSession, client: AsyncClient, page: dict[str, Any], generation: int = 0
) -> str:
    """A grant for the client's login session on this page and generation, issued as
    the relay issues it after its checks."""
    return await CollabService(session).admit(token_of(client), UUID(page["id"]), generation)


def _owner(instance: UUID | None, epoch: int | None = None) -> dict[str, Any]:
    """The instance (and epoch) a call names; nothing for a collab process of 1.0.0."""
    named: dict[str, Any] = {} if instance is None else {"instance_id": str(instance)}
    return named if epoch is None else {**named, "epoch": epoch}


async def collab_auth(
    collab: AsyncClient,
    grant: str,
    page: dict[str, Any],
    generation: int = 0,
    *,
    instance: UUID | None = None,
) -> Any:
    body = {"grant": grant, "page_id": page["id"], "generation": generation, **_owner(instance)}
    return await collab.post("/internal/collab/auth", json=body)


async def load(
    collab: AsyncClient,
    grant: str,
    page: dict[str, Any],
    generation: int = 0,
    *,
    instance: UUID | None = None,
) -> Any:
    return await collab.get(
        f"/internal/collab/pages/{page['id']}",
        params={"generation": generation, **_owner(instance)},
        headers={"X-Herd-Grant": grant},
    )


async def check(
    collab: AsyncClient,
    page: dict[str, Any],
    grants: list[str],
    *,
    unsaved: list[str] | None = None,
    generation: int = 0,
    instance: UUID | None = None,
    epoch: int | None = None,
) -> Any:
    body = {"grants": grants, "unsaved_grants": unsaved or [], "generation": generation}
    body |= _owner(instance, epoch)
    return await collab.post(f"/internal/collab/pages/{page['id']}/check", json=body)


def ydoc(data: bytes = b"\x01\x02state") -> str:
    return base64.b64encode(data).decode()


async def put_live(
    collab: AsyncClient,
    page: dict[str, Any],
    grants: list[str],
    *,
    generation: int = 0,
    content_md: str = "live",
    ydoc_b64: str | None = None,
    session_key: str = "doc-1",
    instance: UUID | None = None,
    epoch: int | None = None,
) -> Any:
    return await collab.put(
        f"/internal/collab/pages/{page['id']}",
        json={
            "generation": generation,
            "ydoc_b64": ydoc_b64 or ydoc(),
            "content_md": content_md,
            "editor_grants": grants,
            "session_key": session_key,
            **_owner(instance, epoch),
        },
    )


async def get_page(client: AsyncClient, page: dict[str, Any]) -> Any:
    r = await client.get(f"/api/pages/{page['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def expect_error(r: Any, status: int, code: str) -> Any:
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    return r.json()["error"]


def instance_id(n: int) -> UUID:
    """A collab instance's id (the process picks its own at start)."""
    return UUID(int=n)


async def announce(
    collab: AsyncClient, instance: UUID, url: str | None = None, *, draining: bool = False
) -> Any:
    """A collab instance's heartbeat (`POST /internal/collab/instances`)."""
    body = {"id": str(instance), "url": url or f"ws://collab-{instance.int}:1234"}
    return await collab.post("/internal/collab/instances", json={**body, "draining": draining})


async def route(session: AsyncSession, page: dict[str, Any]) -> Any:
    """Where the relay sends the next connection of the page (`CollabService.route`)."""
    return await CollabService(session).route(UUID(page["id"]))

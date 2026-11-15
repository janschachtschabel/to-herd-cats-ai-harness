"""Access tokens for tests (plan M8 task 1): `mcp_on` turns the organisation's MCP
switch on, `new_token` makes a token over the API (its clear text in `secret`), and
`resolver` resolves a bearer header the way `/mcp` will (`tokens/resolve.py`)."""

from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.tokens.resolve import TokenResolver
from tests.support.clock import SettableClock


async def mcp_on(
    admin: AsyncClient, *, enabled: bool = True, data_location: str = "external"
) -> dict[str, Any]:
    current = (await admin.get("/api/ai/mcp")).json()
    body = {"enabled": enabled, "data_location": data_location, "version": current["version"]}
    r = await admin.put("/api/ai/mcp", json=body)
    assert r.status_code == 200, r.text
    result: dict[str, Any] = r.json()
    return result


async def new_token(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"name": "Laptop", "mode": "read", "expires_in_days": 30}
    body.update(fields)
    r = await client.post("/api/tokens", json=body)
    assert r.status_code == 201, r.text
    made: dict[str, Any] = r.json()
    return made


def bearer(token: dict[str, Any] | str) -> str:
    secret = token if isinstance(token, str) else token["secret"]
    return f"Bearer {secret}"


def resolver(session: AsyncSession, clock: SettableClock | None = None) -> TokenResolver:
    return TokenResolver(session, get_settings(), clock or SettableClock(datetime.now(UTC)))

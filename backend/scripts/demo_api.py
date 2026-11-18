"""What the demo scripts share: calling the public API and writing messages as the
browser does."""

import asyncio
from typing import Any

import httpx

# The write limit per person (HERD_WRITE_RATE_PER_MINUTE) answers 429 with Retry-After
# when a script writes faster; it waits that long and sends again, a few times.
LIMITED_TRIES = 5


class DemoFailed(Exception):
    """The API refused a step (status and error code in the message)."""


async def call(client: httpx.AsyncClient, method: str, path: str, body: Any = None) -> Any:
    response = await client.request(method, path, json=body)
    for _ in range(LIMITED_TRIES):
        if response.status_code != 429 or "retry-after" not in response.headers:
            break
        await asyncio.sleep(min(int(response.headers["retry-after"]), 60))
        response = await client.request(method, path, json=body)
    if response.status_code >= 300:
        code = response.json().get("error", {}).get("code") if response.content else None
        raise DemoFailed(f"{method} {path}: {response.status_code} {code}")
    return response.json() if response.content else None


def mention(name: str, user_id: str) -> str:
    """A mention as the composer writes it (`@[Name](user:<id>)`)."""
    return f"@[{name}](user:{user_id})"


async def post(
    client: httpx.AsyncClient,
    conversation_id: str,
    body_md: str,
    *,
    parent_id: str | None = None,
    mentions: tuple[str, ...] = (),
) -> str:
    body = {"body_md": body_md, "parent_id": parent_id, "mentions": list(mentions)}
    message = await call(client, "POST", f"/api/conversations/{conversation_id}/messages", body)
    return str(message["id"])

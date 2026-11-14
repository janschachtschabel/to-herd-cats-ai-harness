"""Connector fixtures: `ai_people` are the `people` of an organisation with AI (the
default assignment on a `local` connection to the OpenAI stub), so every member has
`ai.use`; `secret_key` sets `HERD_SECRET_KEY` for the test."""

from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr

from app.core.config import get_settings
from tests.factories_agents import assign_default, make_connection
from tests.factories_dms import People
from tests.support.openai_stub import OpenAIStub

SHARED = "/api/ai/connectors"
PERSONAL = "/api/ai/my-connectors"


@pytest.fixture
def secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr("s" * 48))
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)


@pytest.fixture
async def ai_people(people: People, openai_stub: OpenAIStub, secret_key: None) -> People:
    await assign_default(people.admin, await make_connection(people.admin, openai_stub))
    return people


async def make_connector(client: AsyncClient, path: str = SHARED, **fields: Any) -> dict[str, Any]:
    body = {"name": "GitHub", "auth_kind": "bearer", "secret": {"value": "tok-1"}, **fields}
    response = await client.post(path, json=body)
    assert response.status_code == 201, response.text
    made: dict[str, Any] = response.json()
    return made

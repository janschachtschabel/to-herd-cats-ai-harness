"""Skill fixtures: `lab` is the agent bench (every member has `ai.use`) with a team
space `Labor` (Alice moderator, Bob viewer, Carol none), and helpers to make, read
and change skills over the API."""

from dataclasses import dataclass
from typing import Any

import pytest
from httpx import AsyncClient, Response

from app.core.permissions import SpaceRole
from app.modules.spaces.models import Space, SpaceKind
from tests.factories_agents import Bench
from tests.factories_spaces import MakeSpace

SKILLS = "/api/skills"


@dataclass
class Lab:
    bench: Bench
    space: Space

    @property
    def space_id(self) -> str:
        return str(self.space.id)

    def __getattr__(self, name: str) -> AsyncClient:
        return getattr(self.bench.people, name)  # type: ignore[no-any-return]


@pytest.fixture
async def lab(bench: Bench, make_space: MakeSpace) -> Lab:
    users = bench.people.users
    space = await make_space(
        SpaceKind.TEAM,
        "Labor",
        members=[(users["alice"], SpaceRole.MODERATOR), (users["bob"], SpaceRole.VIEWER)],
    )
    return Lab(bench, space)


async def create(client: AsyncClient, **fields: Any) -> Response:
    body = {"name": "pdf-tools", "description": "Work with PDF files.", "content": "# PDF\n"}
    return await client.post(SKILLS, json={**body, **fields})


async def made(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    response = await create(client, **fields)
    assert response.status_code == 201, response.text
    skill: dict[str, Any] = response.json()
    return skill


async def listed(client: AsyncClient, **params: Any) -> list[dict[str, Any]]:
    response = await client.get(SKILLS, params={"limit": 100, **params})
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items

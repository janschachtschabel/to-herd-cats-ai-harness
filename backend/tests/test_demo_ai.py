"""The demo's agents at work (scripts/demo_ai.py), with the OpenAI stub as the model:
a connection and assignments, two agents with a skill, a conversation with an answer,
a ticket worked up to review, an open page proposal, a pending approval and a memory
page. The worker's runs run in the test's transaction (`work`), as in the agent
tests; the stub's replies are scripted step by step, as against a running stub."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.agents.router  # noqa: F401 -- registers the agent hooks
from app.modules.agents.executor import Executor
from app.modules.agents.executor_repository import claim
from app.modules.users.models import User
from scripts import demo_ai
from scripts.demo_seed import seed
from tests.factories import PASSWORD, login
from tests.support.openai_stub import OpenAIStub
from tests.test_demo_seed import DEMO_PASSWORD, _handle


def _runner(session: AsyncSession) -> Callable[[], Awaitable[None]]:
    """Works every queued run to its end in the test's transaction (a savepoint per
    unit of work), as the worker would."""

    @asynccontextmanager
    async def unit() -> AsyncIterator[AsyncSession]:
        nested = await session.begin_nested()
        try:
            yield session
        except BaseException:
            if nested.is_active:
                await nested.rollback()
            raise
        if nested.is_active:
            await nested.commit()

    async def work() -> None:
        while True:
            async with unit() as claiming:
                claimed = await claim(claiming, 30.0)
            if claimed is None:
                return
            await Executor(unit).execute(claimed)

    return work


@pytest.fixture
async def demo(
    session: AsyncSession,
    make_client: Callable[..., Awaitable[AsyncClient]],
    owner_user: User,
    openai_stub: OpenAIStub,
) -> dict[str, Any]:
    async def connect() -> AsyncClient:
        return await make_client(csrf=True)

    async def script(replies: list[dict[str, Any]]) -> None:
        openai_stub.state.replies.extend(replies)

    ai = demo_ai.Ai(base_url=openai_stub.base_url, script=script, work=_runner(session))
    seeded = await seed(
        connect,
        admin_email=owner_user.email,
        admin_password=PASSWORD,
        people_password=DEMO_PASSWORD,
        settle=lambda: _handle(session),
        wait_seconds=0,
        ai=ai,
    )
    clients = {}
    for key, email in seeded.emails.items():
        clients[key] = await make_client(csrf=True)
        await login(clients[key], email, DEMO_PASSWORD)
    admin = await make_client(csrf=True)
    await login(admin, owner_user.email, PASSWORD)
    return {"seeded": seeded, "clients": clients, "admin": admin, "stub": openai_stub}


async def _get(client: AsyncClient, path: str) -> Any:
    response = await client.get(path)
    assert response.status_code == 200, response.text
    return response.json()


async def test_connection_assignments_agents_and_skill(demo: dict[str, Any]) -> None:
    seeded, admin, people = demo["seeded"], demo["admin"], demo["clients"]
    made = seeded.ai
    assert made is not None
    connection = await _get(admin, f"/api/ai/connections/{made.connection_id}")
    assert (connection["kind"], connection["base_url"]) == ("local", demo["stub"].base_url)
    assignments = await _get(admin, "/api/ai/assignments")
    assert assignments["default"]["connection_id"] == made.connection_id
    for key, has_ai in (("anna", True), ("ben", True), ("clara", False)):
        me = await _get(people[key], "/api/auth/me")
        assert ("ai.use" in me["permissions"]) is has_ai, key
    hilda = await _get(admin, f"/api/agents/{made.agents['hilda']}")
    otto = await _get(admin, f"/api/agents/{made.agents['otto']}")
    assert (hilda["name"], hilda["level"], otto["name"], otto["level"]) == ("Hilda", 1, "Otto", 2)
    skills = await _get(admin, f"/api/agents/{made.agents['otto']}/skills")
    assert [s["name"] for s in skills["skills"]] == ["protokoll"]
    assert skills["skills"][0]["id"] == made.skill_id
    members = await _get(admin, f"/api/spaces/{seeded.space_id}/members?limit=100")
    roles = {m["member_id"]: m["role"] for m in members["items"] if m["member_type"] == "agent"}
    assert roles == {made.agents["hilda"]: "viewer", made.agents["otto"]: "editor"}


async def test_an_answer_a_ticket_in_review_and_a_proposal(demo: dict[str, Any]) -> None:
    seeded, people = demo["seeded"], demo["clients"]
    made = seeded.ai
    ben, anna = people["ben"], people["anna"]
    asked = await _get(ben, f"/api/conversations/{made.dms['ben_hilda']}/messages?limit=100")
    answers = [m["body_md"] for m in asked["items"] if m["kind"] == "agent"]
    assert answers == [demo_ai.LEAVE_ANSWER]
    assert "30 Tage im Jahr" in demo["stub"].state.texts()  # read_page gave the page

    ticket = await _get(anna, f"/api/tickets/{made.ticket_number}")
    assert ticket["status"]["category"] == "review"
    assert ticket["assignee"] == {"type": "agent", "id": made.agents["otto"], "name": "Otto"}
    thread = await _get(anna, f"/api/tickets/{made.ticket_number}/thread")
    said = await _get(anna, f"/api/conversations/{thread['id']}/messages?limit=100")
    assert [m["body_md"] for m in said["items"] if m["kind"] == "agent"] == [demo_ai.TICKET_ANSWER]
    assert "Protokolle beginnen mit Datum" in demo["stub"].state.texts()  # load_skill

    path = f"/api/spaces/{seeded.space_id}/proposals?state=open&limit=100"
    (proposal,) = (await _get(anna, path))["items"]
    assert proposal["page_id"] == seeded.handbook_id
    assert proposal["author"]["type"] == "agent"
    assert proposal["run_id"] == made.runs["proposal"]


async def test_a_pending_approval_and_a_memory_page(demo: dict[str, Any]) -> None:
    seeded, people = demo["seeded"], demo["clients"]
    made = seeded.ai
    run = await _get(people["ben"], f"/api/runs/{made.runs['approval']}")
    assert run["state"] == "waiting"
    (approval,) = (await _get(people["ben"], "/api/approvals?state=pending"))["items"]
    assert (approval["tool"], approval["run_id"]) == ("propose_page_change", run["id"])
    assert approval["id"] == made.approval_id
    page = await _get(people["anna"], f"/api/pages/{made.memory_page_id}")
    assert page["path"] == "_agenten/otto/gedaechtnis"
    assert demo_ai.MEMORY in page["content_md"]
    assert page["updated_by"]["type"] == "agent"


async def test_a_real_model_gets_no_script() -> None:
    assert demo_ai.from_env({}) is None
    ai = demo_ai.from_env(
        {
            "HERD_DEMO_AI_KIND": "openai",
            "HERD_DEMO_AI_MODEL": "gpt-6-luna",
            "HERD_DEMO_AI_KEY_ENV": "HERD_AI_DEMO_KEY",
        }
    )
    assert ai is not None
    assert (ai.kind, ai.base_url, ai.model, ai.key_env, ai.script) == (
        "openai",
        None,
        "gpt-6-luna",
        "HERD_AI_DEMO_KEY",
        None,
    )
    stubbed = demo_ai.from_env(
        {
            "HERD_DEMO_AI_KIND": "local",
            "HERD_DEMO_AI_URL": "http://127.0.0.1:8099/v1",
            "HERD_DEMO_AI_STUB": "http://127.0.0.1:8099",
        }
    )
    assert stubbed is not None and stubbed.script is not None
    assert stubbed.connection_body()["base_url"] == "http://127.0.0.1:8099/v1"
    with pytest.raises(demo_ai.DemoFailed):
        demo_ai.from_env({"HERD_DEMO_AI_KIND": "local"})  # local needs its address

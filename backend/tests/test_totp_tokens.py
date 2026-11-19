"""For a person with TOTP, a new access token (own or an external agent's) needs a
current code (ASVS 5.0 V6.3.4: a token is another way in and must not be easier to
get than a sign-in)."""

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tokens.models import AccessToken
from tests.factories_external_agents import agent_token, make_external
from tests.factories_tokens import mcp_on, new_token
from tests.factories_totp import enroll
from tests.factories_writing import Work
from tests.support.clock import SettableClock

BODY = {"name": "Laptop", "mode": "read", "expires_in_days": 30}


async def _count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(AccessToken)) or 0)


async def test_a_person_with_totp_needs_a_code_for_a_token(
    owner: AsyncClient, session: AsyncSession, totp_time: SettableClock
) -> None:
    await mcp_on(owner)
    enrolled = await enroll(owner, totp_time)
    missing = await owner.post("/api/tokens", json=BODY)
    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "auth.second_factor_required"
    wrong = await owner.post("/api/tokens", json={**BODY, "second_factor_code": "000000"})
    assert wrong.status_code == 422
    assert wrong.json()["error"]["code"] == "auth.second_factor_invalid"
    assert await _count(session) == 0
    made = await new_token(owner, second_factor_code=enrolled.next_code())
    assert made["secret"].startswith("herd_pat_")


async def test_without_totp_a_token_needs_no_code(owner: AsyncClient, totp_time) -> None:
    await mcp_on(owner)
    assert (await owner.post("/api/tokens", json=BODY)).status_code == 201


async def test_an_agent_token_needs_the_issuers_code(
    work: Work, session: AsyncSession, totp_time: SettableClock
) -> None:
    await mcp_on(work.admin)
    agent = await make_external(work)
    enrolled = await enroll(work.admin, totp_time)
    body = {"name": "Codex", "mode": "write", "expires_in_days": 30}
    r = await work.admin.post(f"/api/agents/{agent.id}/tokens", json=body)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "auth.second_factor_required"
    made = await agent_token(work.admin, agent, second_factor_code=enrolled.next_code())
    assert made["secret"].startswith("herd_agt_")

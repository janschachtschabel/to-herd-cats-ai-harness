"""Plan M8 task 1 (global constraints): a token's clear text and its hash appear in no
log line, no audit row, no outbox event and no error, through every token flow:
create, list, use, fail, revoke, the admin's list and revoke."""

import logging
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.outbox import EventOutbox
from app.modules.audit.models import AuditLog
from app.modules.tokens.models import AccessToken
from tests.factories_tokens import bearer, mcp_on, new_token, resolver


async def test_no_token_value_leaks_anywhere(
    session: AsyncSession,
    owner: AsyncClient,
    member_client: AsyncClient,
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    await mcp_on(owner)
    made = await new_token(member_client)
    other = await new_token(member_client, name="zweites")
    await member_client.get("/api/tokens")
    await resolver(session).resolve(bearer(made))
    errors: list[str] = []
    for header in (bearer(made["secret"] + "x"), bearer(made), "Bearer " + "y" * 60):
        if header == bearer(made):
            await member_client.delete(f"/api/tokens/{made['id']}")
        try:
            await resolver(session).resolve(header)
        except AppError as refused:
            errors.append(f"{refused.code} {refused.message} {refused.details}")
    await owner.get("/api/ai/mcp/tokens")
    await owner.delete(f"/api/ai/mcp/tokens/{other['id']}")
    rows = [await session.get(AccessToken, uuid.UUID(t["id"])) for t in (made, other)]
    values = [made["secret"], other["secret"]]
    values += [row.token_hash.hex() for row in rows if row is not None]
    assert len(values) == 4
    audit = [
        f"{e.action} {e.details} {e.target_id}" for e in await session.scalars(select(AuditLog))
    ]
    outbox = [f"{e.type} {e.payload}" for e in await session.scalars(select(EventOutbox))]
    logged = capsys.readouterr()
    records = [str(r.__dict__) for r in caplog.records]
    haystack = "\n".join([*audit, *outbox, *errors, *records, logged.out, logged.err])
    assert "access_token.created" in haystack and "access_token.revoked" in haystack
    for value in values:
        assert value not in haystack
        assert value[-20:] not in haystack  # not even a recognisable piece

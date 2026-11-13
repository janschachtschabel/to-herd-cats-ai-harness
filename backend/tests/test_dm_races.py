"""Opening the same direct message at once, over separate connections with real
commits (tests/real_db.py): one conversation, whoever opens it and in which order."""

import asyncio

from sqlalchemy import func, select

from app.modules.messaging.models import Conversation, ConversationParticipant
from tests.factories import login
from tests.real_db import MakeRealClient, RealDb

N = 6


async def test_concurrent_opens_make_one_conversation(
    real_db: RealDb, make_real_client: MakeRealClient
) -> None:
    owner, member = await make_real_client(), await make_real_client()
    owner_id = (await login(owner, real_db.owner_email))["user"]["id"]
    member_id = (await login(member, real_db.member_email))["user"]["id"]
    opens = [owner.post("/api/dms", json={"user_ids": [member_id]}) for _ in range(N)]
    opens += [member.post("/api/dms", json={"user_ids": [owner_id, member_id]}) for _ in range(N)]
    responses = await asyncio.gather(*opens)
    assert sorted(r.status_code for r in responses) == [200] * (2 * N - 1) + [201]
    assert len({r.json()["id"] for r in responses}) == 1
    async with real_db.database.session_factory() as session:
        conversations = await session.scalar(select(func.count()).select_from(Conversation))
        participants = await session.scalar(
            select(func.count()).select_from(ConversationParticipant)
        )
    assert (conversations, participants) == (1, 2)

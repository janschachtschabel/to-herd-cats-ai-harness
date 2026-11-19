"""Review of M9b Task 18 (R18-1): the idle limit (J7) must end the session of a tab
nobody attends.

The SPA asks the API on its own, with no input of the person: a live event invalidates
query keys (`frontend/src/features/messaging/live.ts`: `message.created` refetches
`GET /api/conversations/unread`, which the app shell always shows), and an open
conversation is asked again every minute (`conversationQuery`, `refetchInterval`).
Each of those is an ordinary request and counts as a use of the session, so in an
organisation where anybody writes, an open tab never becomes idle, although
`docs/ANMELDUNG.md` says an open tab does not count as use.

The test sends exactly what the SPA sends for such a refetch today. A fix lets the
server tell the app's own requests from the person's (a header the SPA sets on
refetches no input caused, say); the requests here then carry that mark."""

from datetime import timedelta

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from app.modules.users.models import User
from tests.factories import login
from tests.support.clock import SettableClock


async def test_an_unattended_tab_does_not_keep_the_session_alive(
    client: AsyncClient,
    owner_user: User,
    session_time: SettableClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "session_idle_hours", 24)
    await login(client, owner_user.email)
    # The person leaves; the tab stays open. Colleagues write now and then, and every
    # `message.created` makes the tab refetch the unread counts by itself.
    for _ in range(30):
        session_time.advance(timedelta(hours=1))
        await client.get("/api/conversations/unread", params={"limit": 100})
    # 30 hours without any input of the person: the session has ended.
    answer = await client.get("/api/auth/me")
    assert answer.status_code == 401, "the tab's own refetches kept the session alive"
    assert answer.json()["error"]["code"] == "auth.session_invalid"

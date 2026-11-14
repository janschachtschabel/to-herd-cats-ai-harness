"""An agent's memory pages and their folders `_agenten/…` are never due for review
(plan M7 task 6): not reminded by the daily pass, not in the tree's filter, not
flagged on the page."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core.models_base import utcnow
from app.core.outbox import EventOutbox
from app.modules.wiki.events import PAGE_REVIEW_DUE
from app.modules.wiki.models import Page
from app.modules.wiki.review_pass import review_next
from tests.factories_tools import tool_context
from tests.factories_writing import Work, alone_in
from tests.test_agent_memory import remember


@pytest.fixture
async def work(work: Work) -> Work:
    """`work`, with Alice the only person who reads its space (memory may go there)."""
    await alone_in(work)
    return work


async def test_memory_pages_are_never_due(work: Work) -> None:
    session = work.bench.session
    ctx = await tool_context(work.bench)
    assert "saved" in (await remember(ctx, work.space.id, "Notiz")).lower()
    page_id = await work.page("Regeln")
    paths = (await session.scalars(select(Page.path).where(Page.space_id == work.space.id))).all()
    assert sorted(paths) == ["_agenten", "_agenten/ava", "_agenten/ava/gedaechtnis", "regeln"]
    old = utcnow() - timedelta(days=400)
    await session.execute(
        update(Page).where(Page.space_id == work.space.id).values(reviewed_at=old)
    )
    space = (await work.admin.get(f"/api/spaces/{work.space.id}")).json()
    r = await work.admin.patch(
        f"/api/spaces/{work.space.id}",
        json={"review_interval_days": 30, "version": space["version"]},
    )
    assert r.status_code == 200, r.text
    while await review_next(session, utcnow()) is not None:
        pass
    events = (
        await session.scalars(select(EventOutbox).where(EventOutbox.type == PAGE_REVIEW_DUE))
    ).all()
    assert [str(e.subject_id) for e in events] == [page_id]
    r = await work.admin.get(
        f"/api/spaces/{work.space.id}/pages/tree", params={"review_due": "true"}
    )
    assert [n["id"] for n in r.json()["items"]] == [page_id]
    tree = (await work.admin.get(f"/api/spaces/{work.space.id}/pages/tree")).json()["items"]
    assert {n["path"]: n["review_due"] for n in tree} == {
        "_agenten": False,
        "_agenten/ava": False,
        "_agenten/ava/gedaechtnis": False,
        "regeln": True,
    }

"""Versions written for an agent (spec 9, plan M6 decision 8): source `agent`, the agent
as author, the run, and the AI mark, in the version list and a version's view. A
page written for an agent names the agent as its last writer and as the creator of a
page it made; the person whose rights the write used stays out of the version."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import Principal
from app.modules.wiki.authorship import Authorship
from app.modules.wiki.models import Page, VersionSource
from app.modules.wiki.service import PageService
from tests.factories_wiki import Wiki, new_page
from tests.test_access import actor_of


async def test_a_save_for_an_agent_is_marked(wiki: Wiki, session: AsyncSession) -> None:
    page = await new_page(wiki.editor, wiki.space_id, "Regeln", content_md="eins")
    agent, run_id = Principal.agent(uuid.uuid4()), uuid.uuid4()
    actor = await actor_of(session, wiki.users["moderator"])
    saved = await PageService(session).update(
        actor,
        uuid.UUID(page["id"]),
        content_md="zwei",
        version=page["version"],
        change_summary="Begründung",
        source=VersionSource.AGENT,
        by=Authorship(agent, run_id),
    )
    assert (saved.updated_by_type, saved.updated_by_id) == (agent.type, agent.id)
    assert saved.collab_generation == 1  # open live sessions end
    r = await wiki.editor.get(f"/api/pages/{page['id']}/versions")
    newest, first = r.json()["items"]
    assert newest["author"] == {"type": "agent", "id": str(agent.id), "name": None}
    assert (newest["source"], newest["run_id"], newest["ai"]) == ("agent", str(run_id), True)
    assert newest["change_summary"] == "Begründung"
    assert (first["source"], first["run_id"], first["ai"]) == ("human", None, False)
    one = await wiki.editor.get(f"/api/pages/{page['id']}/versions/2")
    assert (one.json()["run_id"], one.json()["ai"]) == (str(run_id), True)


async def test_a_page_created_for_an_agent_names_it(wiki: Wiki, session: AsyncSession) -> None:
    agent = Principal.agent(uuid.uuid4())
    actor = await actor_of(session, wiki.users["moderator"])
    page = await PageService(session).create(
        actor,
        wiki.space.id,
        None,
        "Neu",
        "Inhalt",
        source=VersionSource.AGENT,
        by=Authorship(agent, None),
    )
    row = await session.scalar(select(Page).where(Page.id == page.id))
    assert row is not None
    assert (row.created_by_type, row.created_by_id) == (agent.type, agent.id)
    assert (row.updated_by_type, row.updated_by_id) == (agent.type, agent.id)
    r = await wiki.editor.get(f"/api/pages/{page.id}/versions")
    (only,) = r.json()["items"]
    assert (only["author"]["type"], only["source"], only["run_id"], only["ai"]) == (
        "agent",
        "agent",
        None,
        True,
    )

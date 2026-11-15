"""What a token may read (plan M8 decisions 3 and 4): the person's rights ∩ the
token's scope ∩ what the AI policy lets a connection at the organisation's MCP data
location receive, and of the pages only published ones not locked for AI.

The token's actor already carries the scope and the policy (`resolve.py`: its
`ReadScope` lists only such spaces, without drafts), so every service called with it
holds to them; these filters say the same in SQL for lists and searches, built on
the same rules (`core/access.visible_space_ids`, `ai/policy_filters`), so `/mcp`
never needs a rule of its own.
"""

import uuid

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import draft_space_ids, visible_space_ids
from app.modules.ai.policy_filters import ai_readable, ai_space_ids
from app.modules.spaces.models import Space
from app.modules.tokens.resolve import TokenActor
from app.modules.wiki.models import Page
from app.modules.wiki.repository import page_seen


def readable_space_ids(token: TokenActor) -> Select[uuid.UUID]:
    """The ids of the spaces the token may read, as SQL for list filters."""
    org_id = token.actor.org_id
    return visible_space_ids(token.actor).where(Space.id.in_(ai_space_ids(org_id, token.location)))


async def readable_spaces(session: AsyncSession, token: TokenActor) -> list[uuid.UUID]:
    """`readable_space_ids`, sorted."""
    return sorted((await session.scalars(readable_space_ids(token))).all())


def readable_page_ids(token: TokenActor) -> Select[uuid.UUID]:
    """The ids of the pages the token may read, as SQL for an `IN` filter: in a
    readable space, published (a token never sees drafts), not locked for AI."""
    actor, org_id = token.actor, token.actor.org_id
    seen = page_seen(org_id, readable_space_ids(token), draft_space_ids(actor))
    return select(Page.id).where(seen, ai_readable(Page, org_id, token.location)).correlate(None)

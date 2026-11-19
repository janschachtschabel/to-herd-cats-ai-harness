"""What a personal release shows (module review M8 3, H5): under the personal mark the
person releases exactly what she is shown, in full. A call's arguments are shown
whole; a page's new content as its diff against the page now, which stops at
`HERD_DIFF_MAX_LINES` (`proposals/rules.fits`). A change beyond that cannot be shown
in full, so it cannot be released: the gate refuses the call before any card
(`NOT_SHOWN`, the model reads it and the run view shows it to her), and an approval
asked before the limit was lowered cannot be approved (409
`approval.not_shown_in_full`)."""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Actor
from app.core.errors import NotFound
from app.modules.proposals import rules
from app.modules.wiki.visibility import PageReader

PAGE_TOOLS = frozenset({"update_page", "propose_page_change"})  # a diff to show
NOT_SHOWN_CODE = "personal_release.too_large"
NOT_SHOWN = (
    f"Refused ({NOT_SHOWN_CODE}): you have read something through the asking person's "
    "own connection in this run, so she must see exactly what you would write before "
    "she releases it, and this change is too large to show her in full. Nothing was "
    "written and she was not asked. Write a smaller change, or tell her here."
)


async def shown_in_full(
    session: AsyncSession, actor: Actor, tool: str, args: dict[str, Any], *, for_ai: bool
) -> bool:
    """Whether a release card can show the call's content in full (a page it cannot
    find: yes, the call finds nothing either). `for_ai`: read as the run's actor."""
    if tool not in PAGE_TOOLS:
        return True
    reader = PageReader(session)
    page_id = uuid.UUID(str(args["page_id"]))
    try:
        page = await (reader.for_ai(actor, page_id) if for_ai else reader.readable(actor, page_id))
    except NotFound:
        return True
    return rules.fits(page.content_md, str(args["content_md"]))

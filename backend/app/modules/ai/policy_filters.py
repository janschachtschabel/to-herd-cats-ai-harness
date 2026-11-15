"""SQL filters for "readable by AI" (spec 7.3, 11), shared by the agent's tools and
the indexing (M5 tasks 6, 9, 10): applied in the same statement as the rights filter,
so content AI may not see never shows up as a hit, a title or a count.

- `ai_space_ids`: the organisation's spaces whose content AI may read at all (policy
  not `none`); with a data location, only those that allow it (`any`, or `restricted`
  with the location among `allowed_locations`).
- `ai_readable`: pages or attachments in such spaces that are not locked (`no_ai`);
  an attachment also not on a locked page; `ai_page_ids` selects such pages.

Neither knows about rights, drafts or the trash: that is the rights filter's part.
"""

import uuid

from sqlalchemy import ColumnElement, Select, and_, false, literal, or_, select

from app.modules.ai.models import AiPolicy, DataLocation
from app.modules.spaces.models import Space
from app.modules.wiki.models import Attachment, Page


def ai_space_ids(org_id: uuid.UUID, location: DataLocation | None = None) -> Select[uuid.UUID]:
    allowed: ColumnElement[bool]
    if location is None:
        allowed = Space.ai_policy != AiPolicy.NONE
    else:
        allowed = or_(
            Space.ai_policy == AiPolicy.ANY,
            and_(
                Space.ai_policy == AiPolicy.RESTRICTED,
                literal(DataLocation(location).value) == Space.allowed_locations.any_(),
            ),
        )
    # Never correlated: it is also nested in statements over `space` (the tools' filters).
    return select(Space.id).where(Space.org_id == org_id, allowed).correlate(None)


def ai_readable(
    model: type[Page] | type[Attachment],
    org_id: uuid.UUID,
    location: DataLocation | None = None,
) -> ColumnElement[bool]:
    readable = and_(
        model.org_id == org_id,
        model.space_id.in_(ai_space_ids(org_id, location)),
        model.no_ai.is_(false()),
    )
    if model is Attachment:
        open_pages = select(Page.id).where(Page.org_id == org_id, Page.no_ai.is_(false()))
        readable = and_(readable, Attachment.page_id.in_(open_pages))
    return readable


def ai_page_ids(org_id: uuid.UUID, location: DataLocation | None = None) -> Select[uuid.UUID]:
    """The ids of the pages AI may read (`ai_readable`), for an `IN` filter."""
    return select(Page.id).where(ai_readable(Page, org_id, location)).correlate(None)

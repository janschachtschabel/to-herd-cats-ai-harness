"""What the proposal services share: the size bound of diffs and merges, the checks
of a decision, the author rule and the input bounds."""

import asyncio
import uuid

from app.core.access import Actor
from app.core.config import get_settings
from app.core.errors import Conflict, ValidationFailed
from app.core.models_base import utcnow
from app.core.principal import Principal, PrincipalType
from app.modules.proposals import merge
from app.modules.proposals.models import MAX_REASON_CHARS, PageProposal, ProposalState
from app.modules.wiki.models import MAX_CONTENT_CHARS, MAX_TITLE_CHARS, Page


def fits(*texts: str) -> bool:
    """Whether a diff or merge of the texts stays within `HERD_DIFF_MAX_LINES`."""
    return sum(t.count("\n") + 1 for t in texts) <= get_settings().diff_max_lines


async def merge_of(proposal: PageProposal, page: Page) -> merge.Merge | None:
    base = proposal.base_content_md or ""
    if not fits(base, proposal.content_md, page.content_md):
        return None
    return await asyncio.to_thread(merge.merge3, base, proposal.content_md, page.content_md)


def check_open(proposal: PageProposal, version: int) -> None:
    if proposal.state != ProposalState.OPEN:
        raise Conflict(code="proposal.not_open", details={"state": proposal.state})
    if proposal.version != version:
        raise Conflict(
            code="proposal.version_conflict", details={"current_version": proposal.version}
        )


def decide(
    proposal: PageProposal, actor: Actor, state: ProposalState, reason: str | None = None
) -> None:
    proposal.state = state
    proposal.decided_by_id = actor.principal.id
    proposal.decided_at = utcnow()
    proposal.decision_reason = reason
    proposal.version += 1


def check_author(actor: Actor, author: Principal) -> None:
    """An agent, or the acting person themselves."""
    if author.type == PrincipalType.AGENT:
        return
    if author != actor.principal or author.type != PrincipalType.USER:
        raise ValidationFailed(code="proposal.bad_author")


def common(
    content_md: str, reason: str, author: Principal, run_id: uuid.UUID | None
) -> dict[str, object]:
    return {
        "content_md": content_md,
        "reason": reason,
        "author_type": author.type,
        "author_id": author.id,
        "run_id": run_id,
        "state": ProposalState.OPEN,
    }


def _text(value: str, code: str, most: int, *, strip: bool) -> str:
    text = value.strip() if strip else value
    if "\x00" in text or len(text) > most or (strip and not text):
        raise ValidationFailed(code=code)
    return text


def content(value: str) -> str:
    return _text(value, "proposal.invalid_content", MAX_CONTENT_CHARS, strip=False)


def reason(value: str) -> str:
    return _text(value, "proposal.invalid_reason", MAX_REASON_CHARS, strip=True)


def title(value: str) -> str:
    return _text(value, "proposal.invalid_title", MAX_TITLE_CHARS, strip=True)

"""Collab grants (plan M9 decision 16, review R14): the relay checks a browser's session
cookie and hands the collab process a grant `herd_cg_<256 bits>` for exactly one page
and generation instead; the cookie never leaves the API. The internal API loads, saves
and checks only with grants of that page and generation, so a compromised collab
process reaches only pages that are open and no login session.

- Only the SHA-256 of a grant is stored, with its login session, page, generation and
  expiry. A grant lives ten minutes; every check that names it (each open document is
  checked every 5 s) extends it.
- A grant whose login session is deleted (an administrator's sign-out, deactivation,
  a password change, or an hour after a logout or expiry) has no power any more, but
  its row stays until it is cleared away: a check can still tell that unsaved edits
  came through it and end the generation. A grant no one issued for the page and
  generation (unknown, foreign, another generation, cleared) is never found, so it
  never ends a generation.
- Expired grants are cleared in bounded batches when grants are issued, an hour after
  they expired; after a restore none is left (`ops/restore_after.py` empties
  `collab_grant`).

The clear text is never logged, audited, put into a URL or an error.
"""

import hashlib
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.wiki.collab_grant_repository import CollabGrantRepository
from app.modules.wiki.collab_models import CollabGrant

PREFIX = "herd_cg_"
RANDOM_BYTES = 32
GRANT_TTL = timedelta(minutes=10)
# An expired grant is kept this long before it is cleared away (a check may still
# name it while the API was away); then it is unknown.
EXPIRED_GRANT_KEEP = timedelta(hours=1)
EXPIRED_GRANT_BATCH = 500
MAX_GRANT_CHARS = 100  # longer is no grant (the schemas cap what they take)


@dataclass(frozen=True, slots=True)
class GrantRef:
    """A grant issued for the page and generation asked about."""

    id: uuid.UUID
    org_id: uuid.UUID
    session_id: uuid.UUID | None  # None: the login session is gone (no power left)
    expires_at: datetime

    def live(self, now: datetime) -> bool:
        """Not expired and its login session still there (active or ended)."""
        return self.session_id is not None and self.expires_at > now


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8", "surrogatepass")).hexdigest()


def session_ref(session_id: uuid.UUID) -> str:
    """An opaque name of a login session for the collab process's limits per session:
    stable for the session, and nothing to act with."""
    return hashlib.sha256(f"herd-collab-session:{session_id}".encode()).hexdigest()[:32]


async def mint(
    session: AsyncSession,
    *,
    org_id: uuid.UUID,
    session_id: uuid.UUID,
    page_id: uuid.UUID,
    generation: int,
    now: datetime,
) -> str:
    """A new grant for one connection of this login session to this page and
    generation; the clear text goes to the collab process and nowhere else."""
    grants = CollabGrantRepository(session)
    await grants.delete_expired(org_id, now - EXPIRED_GRANT_KEEP, EXPIRED_GRANT_BATCH)
    token = PREFIX + secrets.token_urlsafe(RANDOM_BYTES)
    await grants.add(
        CollabGrant(
            org_id=org_id,
            token_hash=digest(token),
            session_id=session_id,
            page_id=page_id,
            generation=generation,
            expires_at=now + GRANT_TTL,
        )
    )
    return token


async def bound(
    session: AsyncSession,
    tokens: Iterable[str],
    *,
    page_id: uuid.UUID,
    generation: int,
    org_id: uuid.UUID | None = None,
) -> dict[str, GrantRef]:
    """The grants among `tokens` issued for exactly this page and generation (expired
    or powerless ones included), by token. Any other text is simply not found."""
    wanted = {digest(t): t for t in tokens if t.startswith(PREFIX) and len(t) <= MAX_GRANT_CHARS}
    rows = await CollabGrantRepository(session).bound(
        wanted, page_id=page_id, generation=generation, org_id=org_id
    )
    return {
        wanted[h]: GrantRef(row.id, row.org_id, row.session_id, row.expires_at)
        for h, row in rows.items()
    }


async def resolve(
    session: AsyncSession, token: str, *, page_id: uuid.UUID, generation: int, now: datetime
) -> GrantRef | None:
    """The live grant `token` for exactly this page and generation, else None."""
    found = (await bound(session, [token], page_id=page_id, generation=generation)).get(token)
    return found if found is not None and found.live(now) else None


async def renew(session: AsyncSession, grants: Iterable[GrantRef], *, now: datetime) -> None:
    """Ten more minutes for the live ones among these grants (of one organisation)."""
    live = [g for g in grants if g.live(now)]
    if live:
        await CollabGrantRepository(session).extend(
            [g.id for g in live], org_id=live[0].org_id, now=now, until=now + GRANT_TTL
        )

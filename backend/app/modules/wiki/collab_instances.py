"""Collab stage 2 without Redis (plan M9 decision 17, spec 12.4): several collab
instances, each page bound to one of them in PostgreSQL.

- An instance announces itself every 5 s (`announce`: its address from
  HERD_COLLAB_ADVERTISE_URL, and whether it is draining). Silent for INSTANCE_TTL, it
  counts as gone; draining, it gets no new pages; released (`release`, after it has
  saved everything on SIGTERM), its pages are free at once.
- The relay sends every connection of a page to the page's owner (`route`). Without
  a binding that holds (expired, or its instance gone) it binds the page to the live,
  not draining instance with the fewest pages and raises `epoch` atomically. No such
  instance: 502 `collab.unavailable` (the browser tries again).
- Every call of a collab process for a page names its instance; saves and checks also
  the epoch it loaded the page with (`fence`). Whoever is not the owner with the
  current epoch gets 409 `collab.not_owner` (it drops the document and closes with
  4409; the browser reconnects through the relay to the owner), so two instances never
  both write a page: what the stale one did not save in time is lost, the new owner's
  content stays. Each call of the owner extends its binding by OWNER_TTL.
- A collab process of 1.0.0 names no instance (during an upgrade): it is served as
  before while no binding holds for the page; once one does, it is a stale owner.

Heartbeats, "alive since" and expiries all use the database server's clock
(`database_now`), so API nodes whose clocks differ agree on who is alive (review M9b
F11).
"""

import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, Conflict
from app.modules.wiki.collab_owner_repository import (
    CollabInstanceRepository,
    CollabOwnerRepository,
    database_now,
)
from app.modules.wiki.models import Page

HEARTBEAT = timedelta(seconds=5)  # how often an instance announces itself (collab/instance.mjs)
INSTANCE_TTL = 3 * HEARTBEAT
OWNER_TTL = timedelta(seconds=30)
CLAIM_ATTEMPTS = 3


class CollabUnavailable(AppError):
    status_code = 502
    code = "collab.unavailable"


def not_owner() -> Conflict:
    return Conflict(code="collab.not_owner")


@dataclass(frozen=True, slots=True)
class Owner:
    """The collab instance a call comes from and, for saves and checks, the epoch it
    loaded the page with; both None for a collab process of 1.0.0."""

    instance_id: uuid.UUID | None = None
    epoch: int | None = None


LEGACY = Owner()


@dataclass(frozen=True, slots=True)
class Route:
    """Where the relay dials for a page: its owner, its address and the epoch."""

    instance_id: uuid.UUID
    url: str
    epoch: int


async def announce(
    session: AsyncSession, *, instance_id: uuid.UUID, url: str, draining: bool
) -> None:
    now = await database_now(session)
    await CollabInstanceRepository(session).announce(instance_id, url, draining=draining, now=now)


async def release(session: AsyncSession, instance_id: uuid.UUID) -> None:
    await CollabInstanceRepository(session).release(instance_id)


async def route(session: AsyncSession, *, org_id: uuid.UUID, page_id: uuid.UUID) -> Route:
    """The page's owner, or a new one with the next epoch; `CollabUnavailable` when no
    instance can take it."""
    owners = CollabOwnerRepository(session, org_id)
    instances = CollabInstanceRepository(session)
    now = await database_now(session)
    alive_since = now - INSTANCE_TTL
    for _ in range(CLAIM_ATTEMPTS):
        held = await owners.valid(page_id, now=now, alive_since=alive_since)
        if held is not None and held.instance_id is not None:
            instance_id, epoch = held.instance_id, held.epoch
        else:
            chosen = await instances.least_busy(alive_since=alive_since, now=now)
            if chosen is None:
                raise CollabUnavailable()
            claimed = await owners.claim(
                page_id, chosen, now=now, alive_since=alive_since, until=now + OWNER_TTL
            )
            if claimed is None:  # another relay bound it meanwhile: take theirs
                continue
            instance_id, epoch = chosen, claimed
        url = await instances.url(instance_id)
        if url is not None:
            return Route(instance_id, url, epoch)
    raise CollabUnavailable()


async def fence(
    session: AsyncSession, page: Page, owner: Owner, *, lock: bool = False
) -> int | None:
    """The caller owns the page (with its epoch, when it names one): the binding's
    epoch, extended. A caller without instance (1.0.0): None while no binding holds.
    Otherwise 409 `collab.not_owner`. `lock`: hold the binding's row until the
    transaction ends (a save: the page cannot change hands before it commits)."""
    owners = CollabOwnerRepository(session, page.org_id)
    now = await database_now(session)
    page_id, instance_id, epoch = page.id, owner.instance_id, owner.epoch
    if instance_id is None:
        if lock:
            await owners.binding(page_id, lock=True)
        if await owners.valid(page_id, now=now, alive_since=now - INSTANCE_TTL) is not None:
            raise not_owner()
        return None
    bound = await owners.binding(page_id, lock=lock)
    if bound is None or bound.instance_id != instance_id:
        raise not_owner()
    if epoch is not None and bound.epoch != epoch:
        raise not_owner()
    await owners.extend(page_id, instance_id, bound.epoch, until=now + OWNER_TTL)
    return bound.epoch

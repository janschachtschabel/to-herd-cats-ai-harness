"""What messaging reads of tickets, without importing the tickets module (review M4 P9).

Tickets build on messaging (a ticket's thread, its timeline, its notifications), so
messaging must not depend on tickets. The tickets module registers its `TicketHooks`
when its package is imported (`app/modules/tickets/__init__.py`); every process that
has ticket threads imports it (the API's routers, the worker's handlers, the model
registry). Messaging asks through `ticket_hooks()`.
"""

import uuid
from collections.abc import Iterable
from typing import Protocol

from sqlalchemy import ColumnElement, Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute


class TicketNames(Protocol):
    """The names a ticket timeline entry shows, only of the spaces given (review M4 P1)."""

    async def status_names(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]: ...

    async def numbers(self, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, int]: ...


class TicketHooks(Protocol):
    def number(
        self, work_item_id: InstrumentedAttribute[uuid.UUID | None]
    ) -> ColumnElement[int | None]:
        """The number of the ticket with this id, as a column (null without a ticket)."""
        ...

    def key(self, number: int) -> str:
        """The key a person sees for the ticket `number` (`HC-12`)."""
        ...

    def names(
        self, session: AsyncSession, org_id: uuid.UUID, space_ids: Select[uuid.UUID]
    ) -> TicketNames:
        """Names of ticket statuses and keys, only within `space_ids`."""
        ...

    async def people(
        self, session: AsyncSession, org_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> set[uuid.UUID]:
        """The users a ticket thread's ticket is assigned to and was reported by (none
        for other conversations)."""
        ...


_registered: list[TicketHooks] = []


def register_ticket_hooks(hooks: TicketHooks) -> None:
    _registered[:] = [hooks]


def ticket_hooks() -> TicketHooks:
    if not _registered:
        raise RuntimeError("no ticket hooks: import app.modules.tickets first")
    return _registered[0]

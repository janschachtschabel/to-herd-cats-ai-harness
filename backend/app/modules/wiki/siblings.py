"""Slugs and sort orders per parent, remembered across many page creations (an import)."""

import uuid

from app.modules.wiki.models import Page
from app.modules.wiki.repository import PageRepository


class Siblings:
    """Each parent, the slugs and the next sort order under it, read once per parent.
    For many creations in one transaction (an import): it holds the tree lock, so
    nobody else adds, moves or publishes pages of the space meanwhile. Without one,
    `create` reads them each time."""

    def __init__(self) -> None:
        self._locked: set[uuid.UUID] = set()
        self._parents: dict[uuid.UUID, Page | None] = {}
        self._slugs: dict[uuid.UUID | None, set[str]] = {}
        self._orders: dict[uuid.UUID | None, int] = {}

    async def lock(self, pages: PageRepository, space_id: uuid.UUID) -> None:
        """The space's tree lock, taken once (it holds until the transaction ends)."""
        if space_id not in self._locked:
            await pages.lock_tree(space_id)
            self._locked.add(space_id)

    async def parent(
        self, pages: PageRepository, space_id: uuid.UUID, parent_id: uuid.UUID
    ) -> Page | None:
        if parent_id not in self._parents:
            self._parents[parent_id] = await pages.live_in_space(space_id, parent_id)
        return self._parents[parent_id]

    async def slugs(
        self, pages: PageRepository, space_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> set[str]:
        if parent_id not in self._slugs:
            self._slugs[parent_id] = await pages.sibling_slugs(space_id, parent_id)
        return self._slugs[parent_id]

    async def next_order(
        self, pages: PageRepository, space_id: uuid.UUID, parent_id: uuid.UUID | None
    ) -> int:
        if parent_id not in self._orders:
            self._orders[parent_id] = await pages.next_sort_order(space_id, parent_id)
        order = self._orders[parent_id]
        self._orders[parent_id] = order + 1
        return order

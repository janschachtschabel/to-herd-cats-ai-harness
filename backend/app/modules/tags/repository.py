"""The SQL of tags. `TagRepository` is scoped by the actor's organisation and the spaces
it may read (`TagScope`): a tag of a space the actor cannot see is never loaded.
`tags_for` and `subject_ids` serve other modules' lists and filters."""

import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import ColumnElement, Select, and_, delete, func, or_, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import visible_space_ids
from app.core.actor import Actor
from app.core.repository import advisory_xact_lock
from app.modules.tags.models import SubjectType, Tag, Tagging


@dataclass(frozen=True, slots=True)
class TagScope:
    org_id: uuid.UUID
    space_ids: Select[uuid.UUID]  # the spaces the actor may read (SQL)


def tag_repository(session: AsyncSession, actor: Actor) -> "TagRepository":
    """The actor's view of the tags: its organisation, the spaces it may read."""
    return TagRepository(session, TagScope(actor.org_id, visible_space_ids(actor)))


class TagRepository:
    def __init__(self, session: AsyncSession, scope: TagScope) -> None:
        self.session = session
        self.scope = scope

    def _visible(self) -> ColumnElement[bool]:
        return and_(
            Tag.org_id == self.scope.org_id,
            or_(Tag.space_id.is_(None), Tag.space_id.in_(self.scope.space_ids)),
        )

    async def lock_writes(self) -> None:
        """Serialise changes to the organisation's tags (names, versions)."""
        await advisory_xact_lock(self.session, f"tags:{self.scope.org_id}")

    async def add(self, tag: Tag) -> Tag:
        self.session.add(tag)
        await self.session.flush()
        return tag

    async def get(self, tag_id: uuid.UUID) -> Tag | None:
        """As committed now, even if this session loaded it earlier."""
        stmt = (
            select(Tag)
            .where(self._visible(), Tag.id == tag_id)
            .execution_options(populate_existing=True)
        )
        return await self.session.scalar(stmt)

    async def get_many(self, tag_ids: Iterable[uuid.UUID]) -> list[Tag]:
        stmt = select(Tag).where(self._visible(), Tag.id.in_(list(tag_ids)))
        return list((await self.session.scalars(stmt)).all())

    async def name_taken(
        self, space_id: uuid.UUID | None, name: str, *, other_than: uuid.UUID | None = None
    ) -> bool:
        """Whether a tag of the scope (the space, or system-wide) has this name, in
        any case; looks past the actor's view, as the unique index does."""
        in_scope = Tag.space_id.is_(None) if space_id is None else Tag.space_id == space_id
        stmt = select(Tag.id).where(
            Tag.org_id == self.scope.org_id, in_scope, func.lower(Tag.name) == name.lower()
        )
        if other_than is not None:
            stmt = stmt.where(Tag.id != other_than)
        return await self.session.scalar(stmt.limit(1)) is not None

    async def usable_in(self, space_id: uuid.UUID, names: Iterable[str]) -> list[Tag]:
        """The system-wide tags and the space's tags with these names (case ignored)."""
        lowered = [n.lower() for n in names]
        if not lowered:
            return []
        stmt = select(Tag).where(
            self._visible(),
            or_(Tag.space_id.is_(None), Tag.space_id == space_id),
            func.lower(Tag.name).in_(lowered),
        )
        return list((await self.session.scalars(stmt)).all())

    async def page(
        self,
        space_id: uuid.UUID | None,
        after: tuple[str, uuid.UUID] | None,
        limit: int,
        *,
        system_only: bool = False,
    ) -> list[Tag]:
        """By name (case ignored); with `space_id`, the system-wide tags and that
        space's; with `system_only`, the system-wide tags; else every tag the actor
        sees."""
        key = func.lower(Tag.name)
        stmt = select(Tag).where(self._visible()).order_by(key, Tag.id).limit(limit)
        if system_only:
            stmt = stmt.where(Tag.space_id.is_(None))
        elif space_id is not None:
            stmt = stmt.where(or_(Tag.space_id.is_(None), Tag.space_id == space_id))
        if after is not None:
            stmt = stmt.where(tuple_(key, Tag.id) > tuple_(*after))
        return list((await self.session.scalars(stmt)).all())

    async def delete(self, tag: Tag) -> None:
        """Its taggings go with it (foreign key cascade)."""
        await self.session.delete(tag)
        await self.session.flush()

    # --- taggings ------------------------------------------------------------------

    async def replace_for(
        self, subject_type: SubjectType, subject_id: uuid.UUID, tag_ids: list[uuid.UUID]
    ) -> None:
        await self.session.execute(
            delete(Tagging).where(
                Tagging.org_id == self.scope.org_id,
                Tagging.subject_type == subject_type,
                Tagging.subject_id == subject_id,
            )
        )
        if tag_ids:
            rows = [
                {
                    "org_id": self.scope.org_id,
                    "tag_id": tag_id,
                    "subject_type": subject_type,
                    "subject_id": subject_id,
                }
                for tag_id in tag_ids
            ]
            await self.session.execute(insert(Tagging).values(rows).on_conflict_do_nothing())

    async def tags_for(
        self, subject_type: SubjectType, ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, list[Tag]]:
        """The tags on each object, by name, in one query (lists without N+1). The
        callers have checked that the actor may see the objects; the tags on an object
        it may see are ones it may see too."""
        wanted = list(ids)
        found: dict[uuid.UUID, list[Tag]] = defaultdict(list)
        if not wanted:
            return found
        stmt = (
            select(Tagging.subject_id, Tag)
            .join(Tag, Tag.id == Tagging.tag_id)
            .where(
                Tagging.org_id == self.scope.org_id,
                Tagging.subject_type == subject_type,
                Tagging.subject_id.in_(wanted),
            )
            .order_by(func.lower(Tag.name), Tag.id)
        )
        for subject_id, tag in (await self.session.execute(stmt)).all():
            found[subject_id].append(tag)
        return found

    def subject_ids(
        self, subject_type: SubjectType, tag_ids: Iterable[uuid.UUID]
    ) -> Select[uuid.UUID]:
        """The objects carrying any of the tags, as SQL for list filters."""
        return select(Tagging.subject_id).where(
            Tagging.org_id == self.scope.org_id,
            Tagging.subject_type == subject_type,
            Tagging.tag_id.in_(list(tag_ids)),
        )

    async def delete_for(self, subject_type: SubjectType, ids: Iterable[uuid.UUID]) -> None:
        """Drop the tags of objects deleted for good."""
        wanted = list(ids)
        if not wanted:
            return
        await self.session.execute(
            delete(Tagging).where(
                Tagging.org_id == self.scope.org_id,
                Tagging.subject_type == subject_type,
                Tagging.subject_id.in_(wanted),
            )
        )

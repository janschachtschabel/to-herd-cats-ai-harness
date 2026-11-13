"""Tags: the pool (create, rename, recolour, delete) and the tags on objects.

Rights: system-wide tags need `tag.manage` (system admins), a space's tags
`page.moderate` in that space; reading needs only to see the tag (system-wide, or of
a space the actor may read). Tagging a page needs `page.edit` on it, and a space tag
goes only on pages of its own space (422 `tags.wrong_space`). Changes to an
organisation's tags are serialised (`lock_writes`), so the name and version checks
hold under concurrent requests.
"""

import builtins
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import pagination
from app.core.access import Action, Actor, require
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import PageParams, decode_key_cursor, encode_key_cursor
from app.modules.audit.recorder import record
from app.modules.tags.models import SubjectType, Tag
from app.modules.tags.repository import TagRepository, tag_repository
from app.modules.wiki.visibility import PageReader, check_version, touch


def _not_found() -> NotFound:
    return NotFound(code="tags.not_found")


class TagService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def repo(self, actor: Actor) -> TagRepository:
        return tag_repository(self.session, actor)

    async def create(
        self, actor: Actor, name: str, color: str, space_id: uuid.UUID | None = None
    ) -> Tag:
        await self._require_manage(actor, space_id)
        tags = self.repo(actor)
        await tags.lock_writes()
        if await tags.name_taken(space_id, name):
            raise Conflict(code="tags.name_taken")
        tag = await tags.add(Tag(org_id=actor.org_id, space_id=space_id, name=name, color=color))
        await self._audit(actor, "tag.created", tag, {"name": name})
        return tag

    async def list(
        self,
        actor: Actor,
        params: PageParams,
        space_id: uuid.UUID | None = None,
        *,
        system_only: bool = False,
    ) -> pagination.Page[Tag]:
        """The system-wide tags and those of the spaces the actor sees, by name; with
        `space_id`, the system-wide tags and that space's; with `system_only`, only the
        system-wide tags."""
        if system_only and space_id is not None:
            raise ValidationFailed(
                "system and space_id exclude each other", code="validation_failed"
            )
        if space_id is not None:
            await require(self.session, actor, Action.SPACE_READ, space_id)
        after = decode_key_cursor(params.cursor) if params.cursor else None
        rows = await self.repo(actor).page(
            space_id, after, params.limit + 1, system_only=system_only
        )
        items, more = rows[: params.limit], len(rows) > params.limit
        cursor = encode_key_cursor(items[-1].name.lower(), items[-1].id) if more else None
        return pagination.Page[Tag](items=items, next_cursor=cursor)

    async def update(
        self,
        actor: Actor,
        tag_id: uuid.UUID,
        *,
        name: str | None = None,
        color: str | None = None,
        version: int,
    ) -> Tag:
        tag = await self._current(actor, tag_id)
        await self._require_manage(actor, tag.space_id)
        if tag.version != version:
            raise Conflict(code="tags.version_conflict", details={"current_version": tag.version})
        before = {"name": tag.name, "color": tag.color}
        if name is not None and name != tag.name:
            if await self.repo(actor).name_taken(tag.space_id, name, other_than=tag.id):
                raise Conflict(code="tags.name_taken")
            tag.name = name
        if color is not None:
            tag.color = color
        after = {"name": tag.name, "color": tag.color}
        if after != before:
            tag.version += 1
            await self.session.flush()
            await self._audit(actor, "tag.updated", tag, {"from": before, "to": after})
        return tag

    async def delete(self, actor: Actor, tag_id: uuid.UUID) -> None:
        """Takes the tag off everything that carries it."""
        tag = await self._current(actor, tag_id)
        await self._require_manage(actor, tag.space_id)
        details = {"name": tag.name}
        await self.repo(actor).delete(tag)
        await self._audit(actor, "tag.deleted", tag, details)

    async def set_for(
        self,
        actor: Actor,
        subject_type: SubjectType,
        subject_id: uuid.UUID,
        tag_ids: Iterable[uuid.UUID],
        *,
        version: int,
    ) -> builtins.list[Tag]:
        """Replace the object's tags. Pages (the only subjects in M2): `page.edit`, the
        page version the client read (stale: 409), and the page's version is bumped."""
        reader = PageReader(self.session)
        page = await reader.readable(actor, subject_id, lock=True)
        await reader.require_in_space(actor, Action.PAGE_EDIT, page)
        check_version(page, version)
        wanted = builtins.list(dict.fromkeys(tag_ids))
        tags = await self.repo(actor).get_many(wanted)
        if len(tags) != len(wanted):
            raise ValidationFailed(code="tags.not_found")
        if any(t.space_id not in (None, page.space_id) for t in tags):
            raise ValidationFailed(code="tags.wrong_space")
        await self.repo(actor).replace_for(subject_type, page.id, wanted)
        touch(page, actor)
        await self.session.flush()
        details = {"tag_ids": [str(t) for t in wanted]}
        await record(self.session, actor, "page.tags_set", "page", page.id, details)
        return sorted(tags, key=lambda t: (t.name.lower(), t.id))

    async def tags_for(
        self, actor: Actor, subject_type: SubjectType, ids: Iterable[uuid.UUID]
    ) -> dict[uuid.UUID, builtins.list[Tag]]:
        """The tags on objects the caller has already shown the actor may see."""
        return await self.repo(actor).tags_for(subject_type, ids)

    async def _require_manage(self, actor: Actor, space_id: uuid.UUID | None) -> None:
        if space_id is None:
            await require(self.session, actor, Action.TAG_MANAGE)
        else:
            await require(self.session, actor, Action.PAGE_MODERATE, space_id)

    async def _current(self, actor: Actor, tag_id: uuid.UUID) -> Tag:
        """The tag as committed now, with the organisation's tag writes locked."""
        tags = self.repo(actor)
        await tags.lock_writes()
        tag = await tags.get(tag_id)
        if tag is None:
            raise _not_found()
        return tag

    async def _audit(self, actor: Actor, action: str, tag: Tag, details: dict[str, Any]) -> None:
        await record(self.session, actor, action, "tag", tag.id, details)

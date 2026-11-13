"""Live editing through the internal API (spec 9, plan M2 task 8): the collab process
authenticates each connection with the person's session, loads the page's state and
saves through here; it never touches the database.

Every open connection is known by its login session (`session_id`). A session that
merely ended (logout, expiry) of a person who may still edit the page has *ended*:
their edits are saved under their name, only their connection closes. A deactivated
person, a session deleted by an administrator or a password change, and a lost right
count as *revoked*. A save names the sessions whose people edited since the last
save; each is checked again, and if one is revoked, nothing is saved (403 with the
revoked sessions and people).

Generations: every change made outside the live session (Markdown save, restore,
move, trash and restore from the trash) bumps `page.collab_generation`, and so does a
check that finds unsaved edits of a revoked session in the document. A save or a
load for an older generation is refused (409 `collab.generation_ended`), and the
stored Yjs state of an older generation is never handed out again: the collab process
then builds the document from the Markdown.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, actor_for, can
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, Forbidden, Unauthorized
from app.core.metrics import COLLAB_SAVES
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.wiki.collab_models import MAX_YDOC_BYTES
from app.modules.wiki.collab_repository import CollabRepository, page_by_id
from app.modules.wiki.models import Page
from app.modules.wiki.service import PageService
from app.modules.wiki.visibility import PageReader, page_not_found


class StateTooLarge(AppError):
    status_code = 413
    code = "collab.state_too_large"


def session_invalid() -> Unauthorized:
    return Unauthorized(code="collab.session_invalid")


def generation_ended(page: Page) -> Conflict:
    return Conflict(code="collab.generation_ended", details={"generation": page.collab_generation})


@dataclass(frozen=True, slots=True)
class Grant:
    """Who a connection edits as, and the generation it joined."""

    user: User
    session_id: uuid.UUID
    generation: int


@dataclass(frozen=True, slots=True)
class LiveDocument:
    generation: int
    ydoc: bytes | None  # only a state of the current generation
    content_md: str
    title: str


@dataclass(frozen=True, slots=True)
class Revoked:
    session_ids: list[uuid.UUID]
    user_ids: list[uuid.UUID]

    def details(self) -> dict[str, list[str]]:
        return {
            "revoked_session_ids": [str(i) for i in self.session_ids],
            "revoked_user_ids": [str(i) for i in self.user_ids],
        }


@dataclass(frozen=True, slots=True)
class Check:
    generation_ok: bool
    generation: int
    revoked: Revoked
    ended_session_ids: list[uuid.UUID]


@dataclass(frozen=True, slots=True)
class _Editor:
    session_id: uuid.UUID
    user_id: uuid.UUID
    actor: Actor
    ended: bool = False  # the login session ended (logout, expiry); the person may edit


class CollabService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)
        self.auth = AuthService(session, get_settings())

    async def authenticate(self, session_token: str, page_id: uuid.UUID) -> Grant:
        """The person behind the session cookie may edit the page: 401 for no valid
        session, 404 for a page they cannot see (or in the trash), 403 without
        `page.edit`, the same checks as the REST API's."""
        ctx = await self.auth.resolve(session_token)
        if ctx is None or ctx.session_id is None:
            raise session_invalid()
        page = await self._editable(await actor_for(self.session, ctx), page_id)
        return Grant(ctx.user, ctx.session_id, page.collab_generation)

    async def load(
        self, page_id: uuid.UUID, session_id: uuid.UUID, generation: int | None
    ) -> LiveDocument:
        editor = await self._editor(session_id)
        if editor is None:
            raise session_invalid()
        page = await self._editable(editor.actor, page_id)
        if generation is not None and generation != page.collab_generation:
            raise generation_ended(page)
        state = await CollabRepository(self.session, page.org_id).state(page.id)
        ydoc = state.ydoc if state and state.generation == page.collab_generation else None
        return LiveDocument(page.collab_generation, ydoc, page.content_md, page.title)

    async def save(
        self,
        page_id: uuid.UUID,
        *,
        generation: int,
        ydoc: bytes,
        content_md: str,
        session_ids: list[uuid.UUID],
        session_key: str,
    ) -> Page:
        try:
            page = await self._save(page_id, generation, ydoc, content_md, session_ids, session_key)
        except AppError as error:
            COLLAB_SAVES.labels(result=_result(error)).inc()
            raise
        COLLAB_SAVES.labels(result="saved").inc()
        return page

    async def check(
        self,
        page_id: uuid.UUID,
        session_ids: list[uuid.UUID],
        generation: int,
        *,
        unsaved: list[uuid.UUID] | None = None,
    ) -> Check:
        """Whether the connections of these sessions may stay: the generation still
        holds, and which sessions (and their people) may no longer edit.

        If a session with `unsaved` edits may no longer edit, the document holds edits
        no one may save, and every browser that saw them would bring them back on
        reconnecting: the generation ends here (the stored state goes with it)."""
        unsaved = unsaved or []
        # The organisation comes from the page row (the internal API is trusted), so
        # the generation can end even when no session that joined is valid any more.
        page = await page_by_id(self.session, page_id, lock=bool(unsaved))
        if page is None:
            gone = sorted(set([*session_ids, *unsaved]))
            return Check(False, generation, Revoked(gone, []), [])
        editors, revoked = await self._editors([*session_ids, *unsaved], org_id=page.org_id)
        lost = await self._lost(editors, page)
        result = _revoked(revoked, lost)
        ended = sorted(e.session_id for e in editors if e.ended and e not in lost)
        ok = page.trashed_at is None and page.collab_generation == generation
        if ok and set(unsaved) & set(result.session_ids):
            page.collab_generation += 1
            await self.session.flush()
            ok = False
        return Check(ok, page.collab_generation, result, ended)

    async def _save(
        self,
        page_id: uuid.UUID,
        generation: int,
        ydoc: bytes,
        content_md: str,
        session_ids: list[uuid.UUID],
        session_key: str,
    ) -> Page:
        if len(ydoc) > MAX_YDOC_BYTES:
            raise StateTooLarge()
        editors, revoked = await self._editors(session_ids)
        if not editors:
            raise _revoked_error(_revoked(revoked, []))
        live = CollabRepository(self.session, editors[0].actor.org_id)
        page = await live.page(page_id, lock=True)
        if page is None:
            raise page_not_found()
        if page.trashed_at is not None or page.collab_generation != generation:
            raise generation_ended(page)
        lost = await self._lost(editors, page)
        if revoked or lost:
            raise _revoked_error(_revoked(revoked, lost))
        await PageService(self.session).save_live(
            [e.actor for e in editors], page, content_md, session_key=session_key
        )
        await live.put_state(page.id, page.collab_generation, ydoc)
        return page

    async def _editable(self, actor: Actor, page_id: uuid.UUID) -> Page:
        page = await self.reader.readable(actor, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        return page

    async def _editor(self, session_id: uuid.UUID, *, ended: bool = False) -> _Editor | None:
        """The session's person; with `ended`, also for a session that has ended."""
        ctx = await self.auth.resolve_session(session_id)
        if ctx is None and ended:
            ctx = await self.auth.resolve_ended_session(session_id)
            if ctx is not None:
                actor = await actor_for(self.session, ctx)
                return _Editor(session_id, ctx.user.id, actor, ended=True)
        if ctx is None:
            return None
        return _Editor(session_id, ctx.user.id, await actor_for(self.session, ctx))

    async def _editors(
        self, session_ids: list[uuid.UUID], *, org_id: uuid.UUID | None = None
    ) -> tuple[list[_Editor], list[uuid.UUID]]:
        """The sessions still valid or merely ended (in the order given, all of one
        organisation: the given one, else the first valid session's) and the ones that
        are neither."""
        editors: list[_Editor] = []
        revoked: list[uuid.UUID] = []
        for session_id in dict.fromkeys(session_ids):
            editor = await self._editor(session_id, ended=True)
            org = org_id or (editors[0].actor.org_id if editors else None)
            if editor is None or (org is not None and editor.actor.org_id != org):
                revoked.append(session_id)
            else:
                editors.append(editor)
        return editors, revoked

    async def _lost(self, editors: list[_Editor], page: Page) -> list[_Editor]:
        """The editors who may no longer see or edit the page."""
        lost = []
        for editor in editors:
            actor = editor.actor
            if not (
                await can(self.session, actor, Action.SPACE_READ, page.space_id)
                and await self.reader.may_see(actor, page)
                and await can(self.session, actor, Action.PAGE_EDIT, page.space_id)
            ):
                lost.append(editor)
        return lost


def _revoked(invalid: list[uuid.UUID], lost: list[_Editor]) -> Revoked:
    """Sorted, so the answer does not depend on the order asked. The people of
    sessions that ended are not known here (the collab process knows whose session it
    was); `user_ids` names those who lost the right."""
    session_ids = sorted({*invalid, *(e.session_id for e in lost)})
    user_ids = sorted({e.user_id for e in lost})
    return Revoked(session_ids, user_ids)


def _revoked_error(revoked: Revoked) -> Forbidden:
    return Forbidden(code="collab.editors_revoked", details=revoked.details())


def _result(error: AppError) -> str:
    return {
        "collab.generation_ended": "generation_ended",
        "collab.editors_revoked": "revoked",
        "collab.state_too_large": "too_large",
    }.get(error.code, "refused")

"""Live editing through the internal API (spec 9, plan M2 task 8, plan M9 decision 16):
the relay checks a browser's session cookie and hands the collab process a grant for
exactly one page and generation (`collab_grants.py`); the collab process loads, saves
and checks only with such grants and never touches the database.

Every open connection is known by its grant. A grant whose login session merely
ended (logout, expiry) of a person who may still edit the page has *ended*: their
edits are saved under their name, only their connection closes. A deactivated person,
a session deleted by an administrator or a password change, an expired grant and a
lost right count as *revoked* (`collab_editors.py`). A save names the grants whose
people edited since the last save; each is checked again, and if one is revoked or
unknown, nothing is saved (403).

Generations: every change made outside the live session (Markdown save, restore,
move, trash and restore from the trash) bumps `page.collab_generation`, and so does a
check that finds unsaved edits of a revoked grant of this page and generation in the
document; a grant no one issued for them never ends one. A save or a load for an
older generation is refused (409 `collab.generation_ended`), and the stored Yjs state
of an older generation is never handed out again: the collab process then builds the
document from the Markdown.

Instances (plan M9 decision 17, `collab_instances.py`): the relay asks `route` where a
page's connections go; joining, loading, saving and checking name the asking instance
(and saving and checking its epoch), and only the page's owner is served.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, actor_for
from app.core.config import get_settings
from app.core.errors import AppError, Conflict, Forbidden, Unauthorized
from app.core.metrics import COLLAB_LOAD_MUTATIONS, COLLAB_SAVES
from app.core.models_base import utcnow
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.wiki import collab_grants, collab_instances
from app.modules.wiki.collab_editors import Editor, EditorResolver
from app.modules.wiki.collab_instances import LEGACY, Owner
from app.modules.wiki.collab_models import MAX_YDOC_BYTES
from app.modules.wiki.collab_repository import CollabRepository, page_by_id
from app.modules.wiki.models import MAX_CONTENT_CHARS, Page
from app.modules.wiki.service import PageService
from app.modules.wiki.visibility import PageReader, page_not_found


class StateTooLarge(AppError):
    status_code = 413
    code = "collab.state_too_large"


def session_invalid() -> Unauthorized:
    return Unauthorized(code="collab.session_invalid")


def grant_invalid() -> Unauthorized:
    return Unauthorized(code="collab.grant_invalid")


def generation_ended(page: Page) -> Conflict:
    return Conflict(code="collab.generation_ended", details={"generation": page.collab_generation})


def editors_revoked() -> Forbidden:
    """No grant goes into an error: the collab process knows which it sent."""
    return Forbidden(code="collab.editors_revoked")


@dataclass(frozen=True, slots=True)
class Joined:
    """Who a connection edits as, an opaque name of its login session (for the collab
    process's limits per session) and the page's generation."""

    user: User
    session_ref: str
    generation: int
    epoch: int | None  # the asking instance's binding (None: it named none)


@dataclass(frozen=True, slots=True)
class LiveDocument:
    generation: int
    ydoc: bytes | None  # only a state of the current generation
    content_md: str
    title: str
    epoch: int | None


@dataclass(frozen=True, slots=True)
class Check:
    generation_ok: bool
    generation: int
    revoked_grants: list[str]
    ended_grants: list[str]


class CollabService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)
        self.auth = AuthService(session, get_settings())
        self.editors = EditorResolver(session)

    async def admit(self, session_token: str, page_id: uuid.UUID, generation: int) -> str:
        """The relay's check of a browser: the person behind the session cookie may
        edit the page (401 for no valid session, 404 for a page they cannot see or in
        the trash, 403 without `page.edit`, the REST API's checks), and the browser's
        document belongs to the current generation (409). A new grant for this
        connection, page and generation."""
        ctx = await self.auth.resolve(session_token)
        if ctx is None or ctx.session_id is None:
            raise session_invalid()
        page = await self._editable(await actor_for(self.session, ctx), page_id)
        if page.collab_generation != generation:
            raise generation_ended(page)
        return await collab_grants.mint(
            self.session,
            org_id=page.org_id,
            session_id=ctx.session_id,
            page_id=page.id,
            generation=generation,
            now=utcnow(),
        )

    async def route(self, page_id: uuid.UUID) -> collab_instances.Route:
        """Where the relay sends a connection of the page it has just admitted."""
        page = await page_by_id(self.session, page_id)
        if page is None:
            raise page_not_found()
        return await collab_instances.route(
            self.session, org_id=page.org_id, page_id=page.id, now=utcnow()
        )

    async def join(
        self, grant: str, page_id: uuid.UUID, generation: int, instance_id: uuid.UUID | None = None
    ) -> Joined:
        """The collab process admits a connection: its grant is live for this page and
        generation, its person (session active) may still edit the page, and the asking
        instance owns the page."""
        editor = await self._active(grant, page_id, generation)
        page = await self._editable(editor.actor, page_id)
        epoch = await self._fence(page, Owner(instance_id))
        session_ref = collab_grants.session_ref(editor.session_id)
        return Joined(editor.user, session_ref, page.collab_generation, epoch)

    async def load(
        self,
        page_id: uuid.UUID,
        grant: str,
        generation: int,
        instance_id: uuid.UUID | None = None,
    ) -> LiveDocument:
        editor = await self._active(grant, page_id, generation)
        page = await self._editable(editor.actor, page_id)
        if generation != page.collab_generation:
            raise generation_ended(page)
        epoch = await self._fence(page, Owner(instance_id))
        state = await CollabRepository(self.session, page.org_id).state(page.id)
        ydoc = state.ydoc if state and state.generation == page.collab_generation else None
        return LiveDocument(page.collab_generation, ydoc, page.content_md, page.title, epoch)

    async def save(
        self,
        page_id: uuid.UUID,
        *,
        generation: int,
        ydoc: bytes,
        content_md: str,
        grants: list[str],
        session_key: str,
        owner: Owner = LEGACY,
    ) -> Page:
        try:
            page = await self._save(
                page_id, generation, ydoc, content_md, grants, session_key, owner
            )
        except AppError as error:
            COLLAB_SAVES.labels(result=_result(error)).inc()
            raise
        COLLAB_SAVES.labels(result="saved").inc()
        return page

    @staticmethod
    def unrepresentable() -> None:
        """A save the collab process refused itself (its Markdown would not read back
        as the document): counted with the other save results."""
        COLLAB_SAVES.labels(result="unrepresentable").inc()

    @staticmethod
    def load_mutation() -> None:
        """A browser's editor changed a document it had just loaded, before anyone
        typed (review M2 ruling B): it stopped and sent nothing; counted only."""
        COLLAB_LOAD_MUTATIONS.inc()

    async def check(
        self,
        page_id: uuid.UUID,
        grants: list[str],
        generation: int,
        *,
        unsaved: list[str] | None = None,
        owner: Owner = LEGACY,
    ) -> Check:
        """Whether the connections of these grants may stay: the generation still
        holds, and which grants may no longer edit. The live ones are extended.

        If a grant with `unsaved` edits was issued for this page and generation and may
        no longer edit, the document holds edits no one may save, and every browser
        that saw them would bring them back on reconnecting: the generation ends here
        (the stored state goes with it). An unknown grant never ends one."""
        unsaved = unsaved or []
        page = await page_by_id(self.session, page_id, lock=bool(unsaved))
        if page is None:
            return Check(False, generation, sorted({*grants, *unsaved}), [])
        await self._fence(page, owner)
        now = utcnow()
        editors = await self.editors.resolve(
            [*grants, *unsaved], page_id=page.id, generation=generation, now=now, org_id=page.org_id
        )
        lost = await self.editors.lost(editors.valid, page)
        known_revoked = {*editors.powerless, *(e.grant for e in lost)}
        revoked = sorted({*known_revoked, *editors.unknown})
        ended = sorted(e.grant for e in editors.valid if e.ended and e not in lost)
        ok = page.trashed_at is None and page.collab_generation == generation
        if ok and set(unsaved) & known_revoked:
            page.collab_generation += 1
            await self.session.flush()
            ok = False
        await collab_grants.renew(self.session, editors.found, now=now)
        return Check(ok, page.collab_generation, revoked, ended)

    async def _save(
        self,
        page_id: uuid.UUID,
        generation: int,
        ydoc: bytes,
        content_md: str,
        grants: list[str],
        session_key: str,
        owner: Owner,
    ) -> Page:
        if len(ydoc) > MAX_YDOC_BYTES or len(content_md) > MAX_CONTENT_CHARS:
            raise StateTooLarge()
        editors = await self.editors.resolve(
            grants, page_id=page_id, generation=generation, now=utcnow()
        )
        if not editors.valid:
            raise editors_revoked()
        live = CollabRepository(self.session, editors.valid[0].actor.org_id)
        page = await live.page(page_id, lock=True)
        if page is None:
            raise page_not_found()
        await self._fence(page, owner, lock=True)
        if page.trashed_at is not None or page.collab_generation != generation:
            raise generation_ended(page)
        if editors.powerless or editors.unknown or await self.editors.lost(editors.valid, page):
            raise editors_revoked()
        await PageService(self.session).save_live(
            [e.actor for e in editors.valid], page, content_md, session_key=session_key
        )
        await live.put_state(page.id, page.collab_generation, ydoc)
        return page

    async def _active(self, grant: str, page_id: uuid.UUID, generation: int) -> Editor:
        """The person of a live grant for this page and generation whose login session
        is active; 401 `collab.grant_invalid` otherwise."""
        ref = await collab_grants.resolve(
            self.session, grant, page_id=page_id, generation=generation, now=utcnow()
        )
        editor = await self.editors.active(grant, ref) if ref is not None else None
        if editor is None:
            raise grant_invalid()
        return editor

    async def _fence(self, page: Page, owner: Owner, *, lock: bool = False) -> int | None:
        """409 `collab.not_owner` unless the calling instance owns the page."""
        return await collab_instances.fence(self.session, page, owner, now=utcnow(), lock=lock)

    async def _editable(self, actor: Actor, page_id: uuid.UUID) -> Page:
        page = await self.reader.readable(actor, page_id)
        await self.reader.require_in_space(actor, Action.PAGE_EDIT, page)
        return page


def _result(error: AppError) -> str:
    return {
        "collab.generation_ended": "generation_ended",
        "collab.editors_revoked": "revoked",
        "collab.state_too_large": "too_large",
        "collab.not_owner": "not_owner",
    }.get(error.code, "refused")

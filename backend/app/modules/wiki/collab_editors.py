"""Who edits through a live document's grants (`collab_service.py`): each grant named
in a save or a check is looked up for exactly the page and generation, and the person
behind its login session is checked again.

- *valid*: a live grant whose session is active, or merely ended (logout, expiry) while
  the person is still active: their edits may be saved under their name.
- *powerless*: issued for the page and generation, but expired, or its login session
  is gone (an administrator's sign-out, deactivation, a password change), or the
  person was deactivated. Unsaved edits through it end the generation.
- *unknown*: not issued for this page and generation (or cleared away). Named as
  revoked, so its connection closes, but it never ends a generation (R14).
Whether a valid editor may still see and edit the page is `lost()`."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, actor_for, can
from app.core.config import get_settings
from app.modules.auth.service import AuthService
from app.modules.users.models import User
from app.modules.wiki import collab_grants
from app.modules.wiki.collab_grants import GrantRef
from app.modules.wiki.models import Page
from app.modules.wiki.visibility import PageReader


@dataclass(frozen=True, slots=True)
class Editor:
    grant: str
    user: User
    session_id: uuid.UUID
    actor: Actor
    ended: bool = False  # the login session ended (logout, expiry); the person may edit


@dataclass(slots=True)
class Editors:
    valid: list[Editor] = field(default_factory=list)
    powerless: list[str] = field(default_factory=list)
    unknown: list[str] = field(default_factory=list)
    found: list[GrantRef] = field(default_factory=list)


class EditorResolver:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reader = PageReader(session)
        self.auth = AuthService(session, get_settings())

    async def resolve(
        self,
        grants: list[str],
        *,
        page_id: uuid.UUID,
        generation: int,
        now: datetime,
        org_id: uuid.UUID | None = None,
    ) -> Editors:
        """The grants (in the order given, each once) sorted into valid, powerless and
        unknown ones."""
        tokens = list(dict.fromkeys(grants))
        refs = await collab_grants.bound(
            self.session, tokens, page_id=page_id, generation=generation, org_id=org_id
        )
        editors = Editors(found=list(refs.values()))
        for token in tokens:
            ref = refs.get(token)
            if ref is None:
                editors.unknown.append(token)
                continue
            editor = await self._editor(token, ref) if ref.live(now) else None
            if editor is None:
                editors.powerless.append(token)
            else:
                editors.valid.append(editor)
        return editors

    async def active(self, token: str, ref: GrantRef) -> Editor | None:
        """The grant's person while its login session is active (not ended)."""
        if ref.session_id is None:
            return None
        ctx = await self.auth.resolve_session(ref.session_id)
        if ctx is None:
            return None
        return Editor(token, ctx.user, ref.session_id, await actor_for(self.session, ctx))

    async def _editor(self, token: str, ref: GrantRef) -> Editor | None:
        editor = await self.active(token, ref)
        if editor is not None or ref.session_id is None:
            return editor
        ctx = await self.auth.resolve_ended_session(ref.session_id)
        if ctx is None:
            return None
        actor = await actor_for(self.session, ctx)
        return Editor(token, ctx.user, ref.session_id, actor, ended=True)

    async def lost(self, editors: list[Editor], page: Page) -> list[Editor]:
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

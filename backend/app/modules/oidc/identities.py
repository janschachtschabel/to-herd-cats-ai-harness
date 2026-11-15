"""Linked accounts: a person sees and removes their own; with `user.manage` an admin
sees and removes anyone's (only an owner touches an owner's, as for passwords). The
administration's routes (`as_admin`) need `user.manage` for one's own accounts too.

The last way into an account stays: an account without a password keeps its last
linked identity (409 `oidc.last_identity`; set a password first). Removing one is
audited as `user.identity_unlinked` with the provider's key."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, require
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.core.principal import SystemRole
from app.modules.audit.recorder import record
from app.modules.oidc.models import OidcProvider, UserIdentity
from app.modules.oidc.repository import IdentityRepository, ProviderRepository
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

type Linked = tuple[UserIdentity, OidcProvider]


class IdentityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list(
        self, actor: Actor, user_id: uuid.UUID, params: PageParams, *, as_admin: bool = False
    ) -> Page[Linked]:
        await self._target(actor, user_id, write=False, as_admin=as_admin)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        rows = await IdentityRepository(self.session, actor.org_id).page_for_user(
            user_id, after, params.limit + 1
        )
        return id_page(rows, params.limit, lambda row: row[0].id)

    async def unlink(
        self,
        actor: Actor,
        user_id: uuid.UUID,
        identity_id: uuid.UUID,
        *,
        as_admin: bool = False,
    ) -> None:
        user = await self._target(actor, user_id, write=True, as_admin=as_admin)
        await UserRepository(self.session).lock_admin_writes(actor.org_id)
        identities = IdentityRepository(self.session, actor.org_id)
        identity = await identities.get_for_user(user_id, identity_id)
        if identity is None:
            raise NotFound(code="oidc.identity_not_found")
        if user.password_hash is None and await identities.count_for_user(user_id) <= 1:
            raise Conflict(code="oidc.last_identity")
        provider = await ProviderRepository(self.session, actor.org_id).get(identity.provider_id)
        await identities.delete(identity)
        details = {"provider": provider.key if provider else None}
        await record(self.session, actor, "user.identity_unlinked", "user", user_id, details)

    async def _target(
        self, actor: Actor, user_id: uuid.UUID, *, write: bool, as_admin: bool
    ) -> User:
        """The person whose accounts are meant: the caller, or anyone for `user.manage`."""
        if as_admin or actor.principal.id != user_id:
            await require(self.session, actor, Action.USER_MANAGE)
        user = await UserRepository(self.session).get(actor.org_id, user_id)
        if user is None:
            raise NotFound(code="users.not_found")
        owner_of_other = user.system_role == SystemRole.OWNER and actor.principal.id != user_id
        if write and owner_of_other and actor.system_role != SystemRole.OWNER:
            raise Forbidden(code="users.owner_only")
        return user

"""Carrying out an admission (`admission.py`): who the checked claims belong to, and
then the login, the link or the new account, each in the callback's transaction.

- A link (`Link`, or from the profile) adds `user_identity` and audits
  `user.identity_linked` (provider key and how, never the subject or the email).
- A self-registration creates a `member` without a password, language `de`, with the
  personal space every new person gets (open spaces need no membership) and, with
  `admission.SIGNUP_GETS_NO_AI` (question J2), an own AI assignment "no AI". It is
  inactive and awaiting approval (`awaiting_approval_since`; Jan's answer J2: nobody
  gets in without an admin's approval, plan M9 task 5b): no session is opened, and
  `user.signup_pending` (ids only) tells the user administrators. Audited as
  `user.self_registered` by the new person; approving or rejecting it is the people
  administration's (`users/service.py`).
- An email taken between the lookup and the insert (another sign-in, an admin) is
  refused as a link would be (`oidc.link_refused`): nothing is merged unchecked.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import actor_for
from app.core.actor import Actor
from app.core.outbox import emit
from app.core.principal import Principal, SystemRole
from app.modules.ai.assignment_repository import AssignmentRepository
from app.modules.ai.models import UserAssignment
from app.modules.audit.recorder import record
from app.modules.auth.context import AuthContext
from app.modules.oidc.admission import (
    SIGNUP_GETS_NO_AI,
    Admission,
    ExistingUser,
    Link,
    Login,
    Refuse,
    Signup,
    decide,
)
from app.modules.oidc.id_token import IdClaims
from app.modules.oidc.models import OidcProvider, UserIdentity
from app.modules.oidc.providers import rules_of
from app.modules.oidc.repository import IdentityRepository
from app.modules.spaces.service import SpaceService
from app.modules.users.events import USER_SIGNUP_PENDING
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

SIGNUP_LOCALE = "de"


@dataclass(frozen=True, slots=True)
class Admitted:
    user: User
    outcome: str  # login, link or signup (a signup awaits approval: no session)


class Accounts:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id
        self.users = UserRepository(session)
        self.identities = IdentityRepository(session, org_id)

    async def admit(
        self, provider: OidcProvider, claims: IdClaims, now: datetime
    ) -> Admitted | Refuse:
        identity = await self.identities.by_subject(provider.id, claims.sub)
        by_subject = await self._existing(identity.user_id if identity else None)
        by_email = None
        if identity is None and claims.email:
            by_email = _existing(await self.users.get_by_email(self.org_id, claims.email))
        admission: Admission = decide(rules_of(provider), claims, by_subject, by_email)
        match admission:
            case Login(user_id):
                assert identity is not None
                identity.last_login_at = now
                return Admitted(await self._user(user_id), "login")
            case Link(user_id):
                user = await self._user(user_id)
                await self.link(provider, user, claims.sub, now, via="email")
                return Admitted(user, "link")
            case Signup(email, name):
                return await self._signup(provider, claims.sub, email, name, now)
            case Refuse():
                return admission

    async def link(
        self, provider: OidcProvider, user: User, subject: str, now: datetime, *, via: str
    ) -> None:
        await self.identities.add(
            UserIdentity(
                org_id=self.org_id,
                user_id=user.id,
                provider_id=provider.id,
                subject=subject,
                created_at=now,
                last_login_at=now,
            )
        )
        actor = await actor_for(self.session, AuthContext(user=user))
        details = {"provider": provider.key, "via": via}
        await record(self.session, actor, "user.identity_linked", "user", user.id, details)

    async def _signup(
        self, provider: OidcProvider, subject: str, email: str, name: str, now: datetime
    ) -> Admitted | Refuse:
        await self.users.lock_admin_writes(self.org_id)
        if await self.users.get_by_email(self.org_id, email) is not None:
            return Refuse("oidc.link_refused")
        user = User(
            org_id=self.org_id,
            email=email,
            name=name,
            locale=SIGNUP_LOCALE,
            system_role=SystemRole.MEMBER,
            password_hash=None,
            is_active=False,
            awaiting_approval_since=now,
        )
        await self.users.add(user)
        await SpaceService(self.session).create_personal(user)
        if SIGNUP_GETS_NO_AI:
            await AssignmentRepository(self.session, self.org_id).add(
                UserAssignment(org_id=self.org_id, user_id=user.id, no_ai=True)
            )
        await self.identities.add(
            UserIdentity(
                org_id=self.org_id,
                user_id=user.id,
                provider_id=provider.id,
                subject=subject,
                created_at=now,
                last_login_at=now,
            )
        )
        # The new person is the author, though not active yet (`actor_for` refuses
        # an inactive person, so the snapshot is made here; it checks nothing).
        actor = Actor(self.org_id, Principal.user(user.id), SystemRole.MEMBER, frozenset())
        details = {"provider": provider.key, "system_role": SystemRole.MEMBER.value}
        await record(self.session, actor, "user.self_registered", "user", user.id, details)
        await emit(
            self.session,
            type=USER_SIGNUP_PENDING,
            actor=actor,
            space_id=None,
            subject_type="user",
            subject_id=user.id,
            payload={"user_id": str(user.id)},
        )
        return Admitted(user, "signup")

    async def _existing(self, user_id: uuid.UUID | None) -> ExistingUser | None:
        if user_id is None:
            return None
        return _existing(await self.users.get(self.org_id, user_id))

    async def _user(self, user_id: uuid.UUID) -> User:
        user = await self.users.get(self.org_id, user_id)
        assert user is not None
        return user


def _existing(user: User | None) -> ExistingUser | None:
    if user is None:
        return None
    return ExistingUser(user.id, user.is_active, pending=user.awaiting_approval_since is not None)

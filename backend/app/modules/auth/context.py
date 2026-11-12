"""Who is calling: resolved once per request and handed to the services."""

import uuid
from dataclasses import dataclass

from app.core.errors import Forbidden
from app.core.principal import Principal, SystemRole
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User

    @property
    def org_id(self) -> uuid.UUID:
        return self.user.org_id

    @property
    def principal(self) -> Principal:
        return Principal.user(self.user.id)

    @property
    def system_role(self) -> SystemRole:
        return SystemRole(self.user.system_role)


def ensure_can_manage_users(actor: AuthContext) -> None:
    """The one permission check of the people administration (until the central
    `require` replaces it): owners and admins manage people."""
    if actor.system_role not in (SystemRole.OWNER, SystemRole.ADMIN):
        raise Forbidden(code="auth.permission_denied")

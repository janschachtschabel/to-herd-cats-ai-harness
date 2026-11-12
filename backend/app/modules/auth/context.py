"""Who is calling: resolved once per request and handed to the services."""

import uuid
from dataclasses import dataclass

from app.core.principal import Principal, SystemRole
from app.modules.users.models import User


@dataclass(frozen=True, slots=True)
class AuthContext:
    user: User
    # The login session the request came with (None right after login).
    session_id: uuid.UUID | None = None

    @property
    def org_id(self) -> uuid.UUID:
        return self.user.org_id

    @property
    def principal(self) -> Principal:
        return Principal.user(self.user.id)

    @property
    def system_role(self) -> SystemRole:
        return SystemRole(self.user.system_role)

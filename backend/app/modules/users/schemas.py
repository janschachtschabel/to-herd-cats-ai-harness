"""User schemas. `password_hash` is never part of any of them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.password_rule import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.core.principal import SystemRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    system_role: SystemRole
    is_active: bool
    locale: str
    last_login_at: datetime | None
    # Self-registered and waiting for an admin to approve or reject (then null).
    awaiting_approval_since: datetime | None
    version: int


class AdminUserOut(UserOut):
    """A person as the people administration lists them: with whether TOTP is on."""

    totp_enabled: bool

    @classmethod
    def of(cls, user: object, *, totp_enabled: bool) -> "AdminUserOut":
        return cls(**UserOut.model_validate(user).model_dump(), totp_enabled=totp_enabled)


class SignupDecisionIn(BaseModel):
    """Approve or reject a waiting account: the version the client read (409)."""

    model_config = ConfigDict(extra="forbid")

    version: int


class PendingCountOut(BaseModel):
    """How many self-registered accounts wait for approval."""

    count: int


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str | None = Field(
        default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )
    system_role: SystemRole = SystemRole.MEMBER
    locale: str = Field(default="de", pattern=r"^(de|en)$")


class UserUpdate(BaseModel):
    """Fields left out (or null) stay as they are; any other field is refused (422)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_role: SystemRole | None = None
    locale: str | None = Field(default=None, pattern=r"^(de|en)$")
    password: str | None = Field(
        default=None, min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH
    )


class ProfileUpdate(BaseModel):
    """What a person sets about themselves (`PATCH /api/auth/me`)."""

    model_config = ConfigDict(extra="forbid")

    locale: str = Field(pattern=r"^(de|en)$")


class ProfileUpdateIn(ProfileUpdate):
    version: int


class PasswordChangeIn(BaseModel):
    """A person's own new password; the current one proves it is them."""

    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)
    new_password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class UserUpdateIn(UserUpdate):
    """The PATCH body: the changes plus the version the client read."""

    version: int

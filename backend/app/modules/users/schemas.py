"""User schemas. `password_hash` is never part of any of them."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

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
    version: int


class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=10, max_length=200)
    system_role: SystemRole = SystemRole.MEMBER
    locale: str = Field(default="de", pattern=r"^(de|en)$")


class UserUpdate(BaseModel):
    """Fields left out (or null) stay as they are; any other field is refused (422)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    system_role: SystemRole | None = None
    locale: str | None = Field(default=None, pattern=r"^(de|en)$")
    password: str | None = Field(default=None, min_length=10, max_length=200)


class UserUpdateIn(UserUpdate):
    """The PATCH body: the changes plus the version the client read."""

    version: int

from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Action
from app.modules.orgs.schemas import OrgOut
from app.modules.users.schemas import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    """`permissions`: the system-wide actions the caller holds; clients decide what to
    show from these (and from a space's `my_role`), never from the role's name."""

    user: UserOut
    org: OrgOut
    permissions: list[Action]

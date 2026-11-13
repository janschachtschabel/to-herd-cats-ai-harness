from pydantic import BaseModel, EmailStr, Field

from app.core.permissions import Action
from app.modules.orgs.schemas import OrgOut
from app.modules.users.schemas import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    """`permissions`: the system-wide actions the caller holds; clients decide what to
    show from these (and from a space's `my_role`), never from the role's name.
    `ai_model`: with `ai.use`, the name of the model the caller's AI assignment gives
    them (nothing else about the connection); null without."""

    user: UserOut
    org: OrgOut
    permissions: list[Action]
    ai_model: str | None

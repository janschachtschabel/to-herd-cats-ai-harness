from pydantic import BaseModel, EmailStr, Field

from app.modules.orgs.schemas import OrgOut
from app.modules.users.schemas import UserOut


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class MeOut(BaseModel):
    user: UserOut
    org: OrgOut

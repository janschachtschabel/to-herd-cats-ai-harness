"""Second-factor schemas. A secret appears only in `TotpSetupOut`, recovery codes only
in `RecoveryCodesOut`: each answer is the only time they are shown."""

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.password_rule import PASSWORD_MAX_LENGTH
from app.modules.totp.factor import Proof
from app.modules.totp.service import Unavailable

CODE_MAX = 16
RECOVERY_CODE_MAX = 64


class TotpStatusOut(BaseModel):
    """`enabled_at`: when TOTP was turned on (null: off). `unavailable`: why it cannot
    be set up (`no_password`: an account without a password signs in through its
    provider, whose MFA applies; `no_secret_key`: the operator set no
    `HERD_SECRET_KEY`); null when it can."""

    enabled_at: datetime | None
    recovery_codes_left: int
    unavailable: Unavailable | None


class TotpSetupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class TotpSetupOut(BaseModel):
    """The secret in base32 and as an `otpauth://` URI (for a QR code), shown this once."""

    secret: str
    uri: str


class TotpCodeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=CODE_MAX)


class RecoveryCodesOut(BaseModel):
    """Ten recovery codes, shown this once; each signs in once instead of a code."""

    recovery_codes: list[str]


class SecondFactorIn(BaseModel):
    """Exactly one of `code` (six digits from the authenticator) and `recovery_code`."""

    model_config = ConfigDict(extra="forbid")

    code: str | None = Field(default=None, min_length=1, max_length=CODE_MAX)
    recovery_code: str | None = Field(default=None, min_length=1, max_length=RECOVERY_CODE_MAX)

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.code is None) == (self.recovery_code is None):
            raise ValueError("give either code or recovery_code")
        return self

    def proof(self) -> Proof:
        return Proof(code=self.code, recovery_code=self.recovery_code)


class SecondFactorNeededOut(BaseModel):
    """The password (or the provider) was right; the sign-in waits for the second
    factor until `expires_at` (`POST /api/auth/login/second-factor`)."""

    second_factor: Literal["totp"] = "totp"
    expires_at: datetime

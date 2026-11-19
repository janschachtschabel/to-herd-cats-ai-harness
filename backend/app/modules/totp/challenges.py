"""Opening a sign-in that waits for the second factor (`sign_in_challenge`): what the
first step (password or OIDC) leaves instead of a session for a person with TOTP. A
random token of 256 bits goes into the browser's cookie (`cookies.py`); the database
keeps its SHA-256. It lasts `CHALLENGE_MINUTES`."""

import secrets as random
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.core.security import hash_token
from app.modules.totp.models import SignInChallenge
from app.modules.totp.repository import ChallengeRepository
from app.modules.totp.timing import totp_clock
from app.modules.users.models import User

CHALLENGE_MINUTES = 5
MAX_CHALLENGE_FAILURES = 5


@dataclass(frozen=True, slots=True)
class Challenge:
    token: str
    expires_at: datetime


async def open_challenge(
    session: AsyncSession,
    user: User,
    method: str,
    clock: Clock | None = None,
    *,
    reauth: bool = False,
) -> Challenge:
    """A waiting sign-in for `user` whose first step (`password` or `oidc`) passed;
    `reauth`: a fresh provider sign-in meant as the proof before linking."""
    token = random.token_urlsafe(32)
    expires_at = (clock or totp_clock()).now() + timedelta(minutes=CHALLENGE_MINUTES)
    await ChallengeRepository(session).add(
        SignInChallenge(
            org_id=user.org_id,
            user_id=user.id,
            token_hash=hash_token(token),
            method=method,
            reauth=reauth,
            expires_at=expires_at,
        )
    )
    return Challenge(token, expires_at)

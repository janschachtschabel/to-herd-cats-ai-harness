"""SQL of the second factor: the TOTP row, the recovery codes and the sign-ins waiting
for the second factor. Using a time step or a recovery code is one statement each, so
two requests with the same code cannot both pass (ASVS 5.0 V6.5.1)."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.totp.models import SignInChallenge, TotpRecoveryCode, UserTotp


class TotpRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def get(self, user_id: uuid.UUID, *, lock: bool = False) -> UserTotp | None:
        """The person's TOTP row, confirmed or not."""
        stmt = select(UserTotp).where(UserTotp.org_id == self.org_id, UserTotp.user_id == user_id)
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def active(self, user_id: uuid.UUID) -> UserTotp | None:
        """The person's TOTP once confirmed: from then on every sign-in needs it."""
        totp = await self.get(user_id)
        return totp if totp is not None and totp.confirmed_at is not None else None

    async def enabled_among(self, user_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        """Which of these people have a confirmed TOTP."""
        if not user_ids:
            return set()
        rows = await self.session.scalars(
            select(UserTotp.user_id).where(
                UserTotp.org_id == self.org_id,
                UserTotp.user_id.in_(user_ids),
                UserTotp.confirmed_at.is_not(None),
            )
        )
        return set(rows)

    async def start(self, user_id: uuid.UUID, secret_ref: str) -> UserTotp:
        """A new, unconfirmed setup in place of an unconfirmed one."""
        await self.remove(user_id)
        totp = UserTotp(org_id=self.org_id, user_id=user_id, secret_ref=secret_ref)
        self.session.add(totp)
        await self.session.flush()
        return totp

    async def use_step(self, totp_id: uuid.UUID, step: int) -> bool:
        """Accept `step` only if it is newer than every step accepted before; one
        statement, so a code is never accepted twice."""
        used = await self.session.scalar(
            update(UserTotp)
            .where(
                UserTotp.id == totp_id,
                UserTotp.org_id == self.org_id,
                or_(UserTotp.last_step.is_(None), UserTotp.last_step < step),
            )
            .values(last_step=step)
            .returning(UserTotp.id)
        )
        return used is not None

    async def remove(self, user_id: uuid.UUID) -> bool:
        """The person's TOTP and recovery codes are gone; whether there was a TOTP."""
        await self.session.execute(
            delete(TotpRecoveryCode).where(
                TotpRecoveryCode.org_id == self.org_id, TotpRecoveryCode.user_id == user_id
            )
        )
        removed = await self.session.scalar(
            delete(UserTotp)
            .where(UserTotp.org_id == self.org_id, UserTotp.user_id == user_id)
            .returning(UserTotp.id)
        )
        return removed is not None

    async def replace_recovery_codes(self, user_id: uuid.UUID, hashes: Sequence[str]) -> None:
        await self.session.execute(
            delete(TotpRecoveryCode).where(
                TotpRecoveryCode.org_id == self.org_id, TotpRecoveryCode.user_id == user_id
            )
        )
        self.session.add_all(
            TotpRecoveryCode(org_id=self.org_id, user_id=user_id, code_hash=h) for h in hashes
        )
        await self.session.flush()

    async def use_recovery_code(self, user_id: uuid.UUID, code_hash: str) -> bool:
        """The code is deleted by the statement that finds it: usable once."""
        used = await self.session.scalar(
            delete(TotpRecoveryCode)
            .where(
                TotpRecoveryCode.org_id == self.org_id,
                TotpRecoveryCode.user_id == user_id,
                TotpRecoveryCode.code_hash == code_hash,
            )
            .returning(TotpRecoveryCode.id)
        )
        return used is not None

    async def recovery_codes_left(self, user_id: uuid.UUID) -> int:
        count = await self.session.scalar(
            select(func.count())
            .select_from(TotpRecoveryCode)
            .where(TotpRecoveryCode.org_id == self.org_id, TotpRecoveryCode.user_id == user_id)
        )
        return int(count or 0)


class ChallengeRepository:
    """Sign-ins waiting for the second factor, looked up by the hash of the cookie's
    token (the organisation is not known before that)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, challenge: SignInChallenge) -> None:
        self.session.add(challenge)
        await self.session.flush()

    async def find(
        self, token_hash: str, now: datetime, *, lock: bool = False
    ) -> SignInChallenge | None:
        stmt = select(SignInChallenge).where(
            SignInChallenge.token_hash == token_hash, SignInChallenge.expires_at > now
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def count_failure(self, challenge: SignInChallenge, limit: int) -> None:
        """One more wrong code; at `limit` the sign-in is over."""
        if challenge.failures + 1 >= limit:
            await self.drop(challenge)
            return
        challenge.failures += 1
        await self.session.flush()

    async def drop(self, challenge: SignInChallenge) -> None:
        await self.session.execute(
            delete(SignInChallenge).where(SignInChallenge.id == challenge.id)
        )

    async def delete_for_users(self, org_id: uuid.UUID, user_ids: Sequence[uuid.UUID]) -> None:
        """Every waiting sign-in of these people (whatever ends their sessions ends
        these too)."""
        if user_ids:
            await self.session.execute(
                delete(SignInChallenge).where(
                    SignInChallenge.org_id == org_id, SignInChallenge.user_id.in_(user_ids)
                )
            )

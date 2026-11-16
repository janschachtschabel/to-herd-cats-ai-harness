"""SQL of the OIDC module: providers, flows and linked identities, each scoped by the
organisation."""

import uuid
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.oidc.models import OidcFlow, OidcProvider, UserIdentity


class ProviderRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def page(
        self, after: uuid.UUID | None, limit: int, *, enabled_only: bool = False
    ) -> list[OidcProvider]:
        stmt = (
            select(OidcProvider)
            .where(OidcProvider.org_id == self.org_id)
            .order_by(OidcProvider.id)
            .limit(limit)
        )
        if enabled_only:
            stmt = stmt.where(OidcProvider.enabled.is_(True))
        if after is not None:
            stmt = stmt.where(OidcProvider.id > after)
        return list((await self.session.scalars(stmt)).all())

    async def get(self, provider_id: uuid.UUID, *, lock: bool = False) -> OidcProvider | None:
        stmt = select(OidcProvider).where(
            OidcProvider.org_id == self.org_id, OidcProvider.id == provider_id
        )
        if lock:
            stmt = stmt.with_for_update()
        return await self.session.scalar(stmt)

    async def by_key(self, key: str) -> OidcProvider | None:
        return await self.session.scalar(
            select(OidcProvider).where(OidcProvider.org_id == self.org_id, OidcProvider.key == key)
        )

    async def add(self, provider: OidcProvider) -> None:
        self.session.add(provider)
        await self.session.flush()

    async def delete(self, provider: OidcProvider) -> None:
        await self.session.delete(provider)
        await self.session.flush()


class FlowRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def add(self, flow: OidcFlow) -> None:
        self.session.add(flow)
        await self.session.flush()

    async def drop_expired(self, now: datetime) -> None:
        await self.session.execute(
            delete(OidcFlow).where(OidcFlow.org_id == self.org_id, OidcFlow.expires_at <= now)
        )

    async def take(
        self, provider_id: uuid.UUID, state_hash: str, binding_hash: str, now: datetime
    ) -> OidcFlow | None:
        """The flow `state_hash` names, for this provider and browser binding, before it
        expires, deleted in the statement that finds it: a second callback finds
        nothing. A state presented without its binding stays (the right browser may
        still come back with it)."""
        stmt = (
            delete(OidcFlow)
            .where(
                OidcFlow.org_id == self.org_id,
                OidcFlow.provider_id == provider_id,
                OidcFlow.state_hash == state_hash,
                OidcFlow.binding_hash == binding_hash,
                OidcFlow.expires_at > now,
            )
            .returning(OidcFlow)
        )
        return (await self.session.scalars(stmt)).one_or_none()


class IdentityRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def by_subject(self, provider_id: uuid.UUID, subject: str) -> UserIdentity | None:
        return await self.session.scalar(
            select(UserIdentity).where(
                UserIdentity.org_id == self.org_id,
                UserIdentity.provider_id == provider_id,
                UserIdentity.subject == subject,
            )
        )

    async def add(self, identity: UserIdentity) -> None:
        self.session.add(identity)
        await self.session.flush()

    async def page_for_user(
        self, user_id: uuid.UUID, after: uuid.UUID | None, limit: int
    ) -> list[tuple[UserIdentity, OidcProvider]]:
        stmt = (
            select(UserIdentity, OidcProvider)
            .join(OidcProvider, OidcProvider.id == UserIdentity.provider_id)
            .where(UserIdentity.org_id == self.org_id, UserIdentity.user_id == user_id)
            .order_by(UserIdentity.id)
            .limit(limit)
        )
        if after is not None:
            stmt = stmt.where(UserIdentity.id > after)
        return [(row[0], row[1]) for row in (await self.session.execute(stmt)).all()]

    async def get_for_user(self, user_id: uuid.UUID, identity_id: uuid.UUID) -> UserIdentity | None:
        return await self.session.scalar(
            select(UserIdentity).where(
                UserIdentity.org_id == self.org_id,
                UserIdentity.user_id == user_id,
                UserIdentity.id == identity_id,
            )
        )

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            UserIdentity.org_id == self.org_id, UserIdentity.user_id == user_id
        )
        return int(await self.session.scalar(stmt) or 0)

    async def delete(self, identity: UserIdentity) -> None:
        await self.session.delete(identity)
        await self.session.flush()

    async def user_ids_of_provider(self, provider_id: uuid.UUID) -> list[uuid.UUID]:
        """The people linked through the provider."""
        stmt = select(UserIdentity.user_id).where(
            UserIdentity.org_id == self.org_id, UserIdentity.provider_id == provider_id
        )
        return sorted(set(await self.session.scalars(stmt)))


async def encrypted_providers(session: AsyncSession) -> list[OidcProvider]:
    """Every provider with an `enc:` client secret, in every organisation, locked: for
    the key rotation (`scripts/rotate_secrets.py`)."""
    stmt = (
        select(OidcProvider)
        .where(OidcProvider.client_secret_ref.like("enc:%"))
        .order_by(OidcProvider.id)
        .with_for_update()
    )
    return list((await session.scalars(stmt)).all())

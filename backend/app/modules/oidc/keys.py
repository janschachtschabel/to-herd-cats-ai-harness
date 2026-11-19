"""A provider's endpoints and keys, as the flow needs them.

- The endpoints come from discovery the first time a sign-in needs them (or an admin
  checks the provider) and are kept on the provider.
- The JWKS is kept on the provider with the time it was fetched. A token whose `kid`
  is not in it fetches the JWKS again, at most once a minute for the provider across
  every node: the fetch is claimed by one `UPDATE` of `jwks_fetched_at` and committed
  before the provider is asked (a key rotation is picked up, a stream of forged
  `kid`s cannot make us hammer the provider).
"""

import logging
from datetime import timedelta
from typing import Any

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.modules.oidc import protocol
from app.modules.oidc.id_token import IdClaims, IdTokenInvalid, verify_id_token
from app.modules.oidc.models import OidcProvider
from app.modules.oidc.providers import issuers_of

JWKS_REFETCH = timedelta(minutes=1)
logger = logging.getLogger(__name__)


class ProviderKeys:
    def __init__(self, session: AsyncSession, provider: OidcProvider, clock: Clock) -> None:
        self.session = session
        self.provider = provider
        self.clock = clock

    async def endpoint(self) -> str:
        """The authorization endpoint."""
        await self._discovered()
        assert self.provider.authorization_endpoint is not None
        return self.provider.authorization_endpoint

    async def token_endpoint(self) -> str:
        await self._discovered()
        assert self.provider.token_endpoint is not None
        return self.provider.token_endpoint

    async def _discovered(self) -> None:
        p = self.provider
        if p.authorization_endpoint and p.token_endpoint and p.jwks_uri:
            return
        await self.discover()

    async def discover(self) -> None:
        """Discovery now; the endpoints are stored with the caller's transaction."""
        found = await protocol.discover(self.provider.issuer)
        self.provider.authorization_endpoint = found.authorization
        self.provider.token_endpoint = found.token
        self.provider.jwks_uri = found.jwks_uri
        await self.session.flush()

    async def verify(self, raw: str, nonce: str) -> IdClaims:
        jwks = self.provider.jwks or await self.refetch() or {"keys": []}
        try:
            return self._check(raw, jwks, nonce)
        except IdTokenInvalid as invalid:
            if invalid.reason != "kid_unknown":
                return self._refuse(invalid)
        fresh = await self.refetch()
        try:
            return self._check(raw, fresh or jwks, nonce)
        except IdTokenInvalid as invalid:
            return self._refuse(invalid)

    async def refetch(self, *, force: bool = False) -> dict[str, Any] | None:
        """The JWKS fetched again if no node did so within `JWKS_REFETCH` (or `force`:
        an admin's check); None if it was too soon."""
        await self._discovered()
        now = self.clock.now()
        claim = (
            update(OidcProvider)
            .where(OidcProvider.id == self.provider.id)
            .values(jwks_fetched_at=now)
            .returning(OidcProvider.id)
        )
        if not force:
            claim = claim.where(
                or_(
                    OidcProvider.jwks_fetched_at.is_(None),
                    OidcProvider.jwks_fetched_at <= now - JWKS_REFETCH,
                )
            )
        if (await self.session.execute(claim)).scalar_one_or_none() is None:
            return None
        await self.session.commit()  # claimed for every node before the provider answers
        assert self.provider.jwks_uri is not None
        jwks = await protocol.fetch_jwks(self.provider.jwks_uri)
        self.provider.jwks = jwks
        self.provider.jwks_fetched_at = now
        await self.session.flush()
        return jwks

    def _check(self, raw: str, jwks: dict[str, Any], nonce: str) -> IdClaims:
        return verify_id_token(
            raw,
            jwks=jwks,
            issuers=issuers_of(self.provider),
            client_id=self.provider.client_id,
            nonce=nonce,
            now=self.clock.now(),
        )

    def _refuse(self, invalid: IdTokenInvalid) -> IdClaims:
        logger.warning(
            "oidc id token refused",
            extra={"provider": self.provider.key, "reason": invalid.reason},
        )
        raise protocol.ProviderFailure("oidc.id_token_invalid")

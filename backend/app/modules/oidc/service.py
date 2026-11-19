"""OIDC providers, managed with `user.manage` (anyone else: 403
`auth.permission_denied`, like every `/api/admin` route).

- `google`: the preset (`providers.py`); the admin gives only the client id, the
  secret, self-registration and domains. Issuer, scopes and `trust_email` are fixed
  (422 `oidc.preset_fixed`); a secret is required (Google issues confidential
  clients only). `generic`: issuer (https, through the egress rules, 422
  `oidc.url_not_allowed`), scopes with `openid`, an optional secret.
- Self-registration needs at least one domain (422 `oidc.domains_required`); domains
  are kept lower case and exact (422 `oidc.domain_invalid`). At a generic provider it
  also needs `trust_email` (422 `oidc.signup_needs_trust`): a provider not trusted for
  addresses may not create accounts under them either (module review M9a, N4).
- A provider is switched on only with `HERD_PUBLIC_URL` (422
  `oidc.public_url_missing`): the redirect URI is derived from it.
- The secret arrives as a value (stored `enc:`) or an `env:HERD_OIDC_*` name; it is
  in no answer, audit entry or log line. A new issuer forgets the discovered
  endpoints and keys.
- Every write names the version it read (409 `oidc.version_conflict`); deleting a
  provider removes the accounts linked through it and its open flows, and ends every
  session of the people linked through it (as unlinking would, ASVS 5.0 V7.4.3; module
  review M9a, N5) but the one the deleting administrator acts with.
- `check` runs discovery and fetches the JWKS now, and reports a fixed code.
"""

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.access import Action, Actor, require
from app.core.clock import SYSTEM_CLOCK
from app.core.config import get_settings
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.pagination import Page, PageParams, decode_id_cursor, id_page
from app.modules.audit.recorder import record
from app.modules.auth.repository import SessionRepository
from app.modules.oidc import protocol
from app.modules.oidc.flow import callback_path, public_base
from app.modules.oidc.keys import ProviderKeys
from app.modules.oidc.models import OidcProvider, ProviderKind
from app.modules.oidc.providers import (
    GOOGLE_ISSUER,
    GOOGLE_NAME,
    GOOGLE_SCOPES,
    normalize_domain,
)
from app.modules.oidc.repository import IdentityRepository, ProviderRepository
from app.modules.oidc.schemas import OidcSecretIn, ProviderCheckOut, ProviderCreate, ProviderUpdate

_AUDITED = ("name", "issuer", "client_id", "scopes", "trust_email", "allow_signup", "enabled")
DEFAULT_SCOPES = "openid email profile"


def provider_not_found() -> NotFound:
    return NotFound(code="oidc.not_found")


def callback_url(provider: OidcProvider) -> str | None:
    try:
        return public_base(get_settings()) + callback_path(provider.key)
    except ValidationFailed:
        return None


class ProviderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _repo(self, actor: Actor) -> ProviderRepository:
        await require(self.session, actor, Action.USER_MANAGE)
        return ProviderRepository(self.session, actor.org_id)

    async def list(self, actor: Actor, params: PageParams) -> Page[OidcProvider]:
        repo = await self._repo(actor)
        after = decode_id_cursor(params.cursor) if params.cursor else None
        return id_page(await repo.page(after, params.limit + 1), params.limit, lambda p: p.id)

    async def get(self, actor: Actor, provider_id: uuid.UUID) -> OidcProvider:
        repo = await self._repo(actor)
        return _found(await repo.get(provider_id))

    async def create(self, actor: Actor, data: ProviderCreate) -> OidcProvider:
        repo = await self._repo(actor)
        google = data.kind == ProviderKind.GOOGLE
        if google and (data.issuer is not None or data.scopes is not None or data.trust_email):
            raise ValidationFailed(code="oidc.preset_fixed")
        if google and data.client_secret is None:
            raise ValidationFailed(code="oidc.secret_required")
        if not google and (data.issuer is None or data.key is None or data.name is None):
            raise ValidationFailed(code="oidc.fields_required")
        key = data.key or ProviderKind.GOOGLE.value
        if await repo.by_key(key) is not None:
            raise Conflict(code="oidc.key_taken")
        provider = OidcProvider(
            org_id=actor.org_id,
            key=key,
            name=data.name or GOOGLE_NAME,
            kind=data.kind,
            issuer=GOOGLE_ISSUER if google else _issuer(data.issuer or ""),
            client_id=data.client_id,
            client_secret_ref=_secret_ref(data.client_secret),
            scopes=GOOGLE_SCOPES if google else _scopes(data.scopes or DEFAULT_SCOPES),
            trust_email=data.trust_email,
            allow_signup=data.allow_signup,
            allowed_domains=_domains(data.allowed_domains),
            enabled=data.enabled,
        )
        _consistent(provider)
        await repo.add(provider)
        details = {"key": provider.key, "kind": provider.kind}
        await record(
            self.session, actor, "oidc_provider.created", "oidc_provider", provider.id, details
        )
        return provider

    async def update(
        self, actor: Actor, provider_id: uuid.UUID, data: ProviderUpdate
    ) -> OidcProvider:
        repo = await self._repo(actor)
        provider = _found(await repo.get(provider_id, lock=True))
        if provider.version != data.version:
            raise Conflict(code="oidc.version_conflict")
        google = provider.kind == ProviderKind.GOOGLE
        if google and (data.issuer is not None or data.scopes is not None or data.trust_email):
            raise ValidationFailed(code="oidc.preset_fixed")
        before = {name: getattr(provider, name) for name in _AUDITED}
        fields = data.model_fields_set
        if data.name is not None:
            provider.name = data.name
        if data.issuer is not None and data.issuer != provider.issuer:
            provider.issuer = _issuer(data.issuer)
            _forget_discovery(provider)
        if data.client_id is not None:
            provider.client_id = data.client_id
        if data.scopes is not None:
            provider.scopes = _scopes(data.scopes)
        for name in ("trust_email", "allow_signup", "enabled"):
            if getattr(data, name) is not None:
                setattr(provider, name, getattr(data, name))
        if data.allowed_domains is not None:
            provider.allowed_domains = _domains(data.allowed_domains)
        if "client_secret" in fields and data.client_secret is not None:
            provider.client_secret_ref = _secret_ref(data.client_secret)
        _consistent(provider)
        provider.version += 1
        await self.session.flush()
        details: dict[str, Any] = {
            "changes": sorted(n for n, old in before.items() if getattr(provider, n) != old)
        }
        if data.allowed_domains is not None:
            details["domains"] = len(provider.allowed_domains)
        if data.client_secret is not None:
            details["secret_replaced"] = True
        await record(
            self.session, actor, "oidc_provider.updated", "oidc_provider", provider.id, details
        )
        return provider

    async def delete(
        self,
        actor: Actor,
        provider_id: uuid.UUID,
        version: int,
        *,
        current_session: uuid.UUID | None = None,
    ) -> None:
        repo = await self._repo(actor)
        provider = _found(await repo.get(provider_id, lock=True))
        if provider.version != version:
            raise Conflict(code="oidc.version_conflict")
        people = await IdentityRepository(self.session, actor.org_id).user_ids_of_provider(
            provider.id
        )
        details = {"key": provider.key, "people": len(people)}
        await repo.delete(provider)
        await SessionRepository(self.session).delete_for_users(
            actor.org_id, people, keep=current_session
        )
        await record(
            self.session, actor, "oidc_provider.deleted", "oidc_provider", provider_id, details
        )

    async def check(self, actor: Actor, provider_id: uuid.UUID) -> ProviderCheckOut:
        repo = await self._repo(actor)
        provider = _found(await repo.get(provider_id))
        if provider.client_secret_ref is not None:
            try:
                secrets.resolve(provider.client_secret_ref)
            except secrets.SecretUnavailable:
                return ProviderCheckOut(ok=False, code="oidc.secret_unavailable")
        keys = ProviderKeys(self.session, provider, SYSTEM_CLOCK)
        try:
            await keys.discover()
            await keys.refetch(force=True)
        except protocol.ProviderFailure as failure:
            return ProviderCheckOut(ok=False, code=failure.code)
        return ProviderCheckOut(ok=True, code=None)


def _found(provider: OidcProvider | None) -> OidcProvider:
    if provider is None:
        raise provider_not_found()
    return provider


def _issuer(url: str) -> str:
    try:
        protocol.check_url(url)
    except protocol.ProviderFailure:
        raise ValidationFailed(code="oidc.url_not_allowed") from None
    return url


def _scopes(scopes: str) -> str:
    if "openid" not in scopes.split():
        raise ValidationFailed(code="oidc.scopes_invalid")
    return scopes


def _domains(raw: list[str]) -> list[str]:
    try:
        return sorted({normalize_domain(d) for d in raw})
    except ValueError:
        raise ValidationFailed(code="oidc.domain_invalid") from None


def _consistent(provider: OidcProvider) -> None:
    if provider.allow_signup and not provider.allowed_domains:
        raise ValidationFailed(code="oidc.domains_required")
    if provider.allow_signup and provider.kind == ProviderKind.GENERIC and not provider.trust_email:
        raise ValidationFailed(code="oidc.signup_needs_trust")
    if provider.enabled:
        public_base(get_settings())


def _forget_discovery(provider: OidcProvider) -> None:
    provider.authorization_endpoint = None
    provider.token_endpoint = None
    provider.jwks_uri = None
    provider.jwks = None
    provider.jwks_fetched_at = None


def _secret_ref(secret: OidcSecretIn | None) -> str | None:
    if secret is None:
        return None
    if secret.env is not None:
        return secrets.env_ref(secret.env, secrets.OIDC_ENV_PREFIX)
    assert secret.value is not None
    return secrets.encrypt(secret.value.get_secret_value())

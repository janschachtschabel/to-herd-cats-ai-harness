"""Signing in through an OpenID provider (plan M9 decision 12): authorization code with
PKCE (S256), `state` and `nonce`, bound to the browser.

- `start`: a fresh `state`, `nonce`, verifier and browser binding (each 256 bits);
  Postgres keeps the SHA-256 of state and binding, nonce and verifier, for
  `FLOW_MINUTES`. The binding goes into the HttpOnly cookie `herd_oidc` (SameSite=Lax,
  path `/api/auth/oidc`; over https `__Host-herd_oidc` on path `/`, see
  `auth/cookies.py`): a callback from another browser (login CSRF, a stolen
  link) finds no flow. The redirect URI is `HERD_PUBLIC_URL` plus the provider's
  callback path, never taken from the request; without that address (or with plain
  http other than localhost) there is no sign-in (`oidc.public_url_missing`).
  Started from the profile (`link_session`), the flow links the provider's account to
  the person of that login session.
- `finish`: the flow is deleted in the statement that finds it (provider, state,
  binding, not expired) and that is committed before the provider is asked, so it is
  used once. Then the code is exchanged, the ID token checked (`id_token.py`; an
  unknown `kid` fetches the JWKS again, at most once a minute across every node) and
  the admission carried out (`accounts.py`). The answer is a page of the app with a
  fixed code, never the provider's words. A self-registration opens no session: the
  account awaits an admin's approval (`/login?error=oidc.account_pending`).

Start and callback count per client address (`HERD_OIDC_RATE_PER_MINUTE`). Nothing of
the claims, the code or the tokens is logged; the metric counts outcomes by code.
"""

import hashlib
import secrets as random
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import quote, urlencode, urlsplit

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import clock as clocks
from app.core import secrets
from app.core.clock import Clock
from app.core.config import Settings
from app.core.errors import NotFound, RateLimited, ValidationFailed
from app.core.ratelimit import RateLimiter, limit_key
from app.modules.auth.context import AuthContext
from app.modules.auth.service import AuthService
from app.modules.auth.sign_in_log import log_sign_in
from app.modules.oidc import protocol
from app.modules.oidc.accounts import Accounts, Admitted
from app.modules.oidc.admission import Refuse
from app.modules.oidc.keys import ProviderKeys
from app.modules.oidc.metrics import count_outcome
from app.modules.oidc.models import OidcFlow, OidcProvider
from app.modules.oidc.providers import extra_parameters
from app.modules.oidc.repository import FlowRepository, IdentityRepository, ProviderRepository
from app.modules.orgs.repository import OrganizationRepository

FLOW_MINUTES = 10
BINDING_COOKIE = "herd_oidc"
COOKIE_PATH = "/api/auth/oidc"
LOGIN_PAGE = "/login"
PROFILE_PAGE = "/profile"
PENDING = "oidc.account_pending"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def callback_path(key: str) -> str:
    return f"{COOKIE_PATH}/{key}/callback"


def public_base(settings: Settings) -> str:
    public = settings.public_url
    parts = urlsplit(public) if public else None
    if parts is None or (parts.scheme != "https" and parts.hostname not in _LOCAL_HOSTS):
        raise ValidationFailed(code="oidc.public_url_missing")
    return public.rstrip("/")  # type: ignore[union-attr]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _challenge(verifier: str) -> str:
    import base64  # noqa: PLC0415

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True, slots=True)
class Started:
    url: str
    binding: str


@dataclass(frozen=True, slots=True)
class Finished:
    location: str
    outcome: str  # the metric's and the log's word
    session_token: str | None = None
    user_id: uuid.UUID | None = None


class FlowService:
    def __init__(
        self, session: AsyncSession, settings: Settings, clock: Clock | None = None
    ) -> None:
        self.session = session
        self.settings = settings
        self.clock = clock if clock is not None else clocks.SYSTEM_CLOCK

    async def _limit(self, ip: str | None) -> bool:
        limiter = RateLimiter(self.session, limit=self.settings.oidc_rate_per_minute)
        return await limiter.acquire(f"oidc:{limit_key(ip)}", self.clock.now()) is not None

    async def _provider(self, key: str) -> tuple[ProviderRepository, OidcProvider]:
        org = await OrganizationRepository(self.session).get_default()
        if org is None:
            raise NotFound(code="oidc.not_found")
        providers = ProviderRepository(self.session, org.id)
        provider = await providers.by_key(key)
        if provider is None or not provider.enabled:
            raise NotFound(code="oidc.not_found")
        return providers, provider

    async def start(
        self, key: str, ip: str | None, *, link_session: AuthContext | None = None
    ) -> Started:
        if not await self._limit(ip):
            raise RateLimited(code="oidc.rate_limited")
        _, provider = await self._provider(key)
        base = public_base(self.settings)
        authorization = await ProviderKeys(self.session, provider, self.clock).endpoint()
        state, nonce, binding = (random.token_urlsafe(32) for _ in range(3))
        verifier = random.token_urlsafe(48)
        now = self.clock.now()
        flows = FlowRepository(self.session, provider.org_id)
        await flows.drop_expired(now)
        await flows.add(
            OidcFlow(
                org_id=provider.org_id,
                provider_id=provider.id,
                state_hash=_hash(state),
                binding_hash=_hash(binding),
                nonce=nonce,
                verifier=verifier,
                link_session_id=link_session.session_id if link_session else None,
                expires_at=now + timedelta(minutes=FLOW_MINUTES),
            )
        )
        query = {
            "response_type": "code",
            "client_id": provider.client_id,
            "redirect_uri": base + callback_path(provider.key),
            "scope": provider.scopes,
            "state": state,
            "nonce": nonce,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            **extra_parameters(provider),
        }
        return Started(f"{authorization}?{urlencode(query, quote_via=quote)}", binding)

    async def finish(
        self,
        key: str,
        ip: str | None,
        *,
        binding: str | None,
        state: str | None,
        code: str | None,
        error: str | None,
    ) -> Finished:
        finished = await self._finish(key, ip, binding=binding, state=state, code=code, error=error)
        log_sign_in("oidc", finished.outcome, client=ip, user_id=finished.user_id, provider=key)
        return finished

    async def _finish(
        self,
        key: str,
        ip: str | None,
        *,
        binding: str | None,
        state: str | None,
        code: str | None,
        error: str | None,
    ) -> Finished:
        if not await self._limit(ip):
            return _refused("oidc.rate_limited", None)
        try:
            providers, provider = await self._provider(key)
        except NotFound:
            return _refused("oidc.unavailable", None)
        flow = None
        if binding and state:
            flows = FlowRepository(self.session, provider.org_id)
            flow = await flows.take(provider.id, _hash(state), _hash(binding), self.clock.now())
        if flow is None:
            return _refused("oidc.flow_invalid", None)
        await self.session.commit()  # the flow is used up, whatever follows
        linking = flow.link_session_id
        if error is not None or not code:
            return _refused(
                "oidc.denied" if error == "access_denied" else "oidc.provider_error", linking
            )
        try:
            secret = (
                secrets.resolve(provider.client_secret_ref).get_secret_value()
                if provider.client_secret_ref
                else None
            )
            base = public_base(self.settings)
        except (secrets.SecretUnavailable, ValidationFailed):
            return _refused("oidc.provider_error", linking)
        keys = ProviderKeys(self.session, provider, self.clock)
        try:
            token_endpoint = await keys.token_endpoint()
            raw = await protocol.exchange_code(
                protocol.TokenRequest(
                    endpoint=token_endpoint,
                    client_id=provider.client_id,
                    secret=secret,
                    code=code,
                    verifier=flow.verifier,
                    redirect_uri=base + callback_path(provider.key),
                )
            )
            claims = await keys.verify(raw, flow.nonce)
        except protocol.ProviderFailure as failure:
            return _refused(failure.code, linking)
        if linking is not None:
            return await self._link(provider, linking, claims.sub)
        now = self.clock.now()
        admitted = await Accounts(self.session, provider.org_id).admit(provider, claims, now)
        if isinstance(admitted, Refuse):
            return _refused(admitted.code, None)
        return await self._signed_in(admitted, now)

    async def _signed_in(self, admitted: Admitted, now: datetime) -> Finished:
        if admitted.outcome == "signup":  # waits for approval (plan M9 task 5b)
            count_outcome(admitted.outcome)
            location = f"{LOGIN_PAGE}?{urlencode({'error': PENDING})}"
            return Finished(location, admitted.outcome, user_id=admitted.user.id)
        token = await AuthService(self.session, self.settings).open_session(admitted.user, now)
        count_outcome(admitted.outcome)
        return Finished("/", admitted.outcome, token, admitted.user.id)

    async def _link(self, provider: OidcProvider, session_id: uuid.UUID, subject: str) -> Finished:
        auth = await AuthService(self.session, self.settings).resolve_session(session_id)
        if auth is None:
            return _refused("oidc.flow_invalid", session_id)
        identities = IdentityRepository(self.session, provider.org_id)
        existing = await identities.by_subject(provider.id, subject)
        if existing is not None and existing.user_id != auth.user.id:
            return _refused("oidc.identity_taken", session_id)
        if existing is None:
            now = self.clock.now()
            await Accounts(self.session, provider.org_id).link(
                provider, auth.user, subject, now, via="profile"
            )
        count_outcome("profile_link")
        location = f"{PROFILE_PAGE}?{urlencode({'linked': provider.key})}"
        return Finished(location, "profile_link", user_id=auth.user.id)


def _refused(code: str, linking: uuid.UUID | None) -> Finished:
    count_outcome(code.removeprefix("oidc."))
    page, name = (PROFILE_PAGE, "link_error") if linking is not None else (LOGIN_PAGE, "error")
    return Finished(f"{page}?{urlencode({name: code})}", code.removeprefix("oidc."))

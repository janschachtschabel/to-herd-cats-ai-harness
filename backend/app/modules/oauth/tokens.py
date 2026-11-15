"""An OAuth connector's access token for a call, renewed when it is about to expire
(`EXPIRY_MARGIN`) or after the server answered 401 with it (plan M8 task 8).

Renewal runs in a transaction of its own (`open_unit`) that locks the connector row
(`FOR UPDATE`) before it asks the authorization server: a second worker that wants
to renew waits for the lock, then finds the token renewed (it differs from the one it
used, or no longer expires soon) and takes it without a request of its own. That
matters: providers rotate refresh tokens (GitHub, GitLab), so a second refresh with
the old one would fail. The new tokens commit before the lock is released.

- The provider refuses the refresh token (`invalid_grant`): the tokens are dropped,
  the connector is not connected any more (`NotAuthorized`: someone connects again).
- The provider cannot be reached or fails otherwise: the tokens stay
  (`CredentialUnavailable`), a later call tries again.
- A provider that sends no new refresh token keeps the old one (RFC 6749 6).

The plaintext exists only in the returned headers and the request to the provider;
the log line `oauth.token_request` names the connector, the grant, the status and
the duration.
"""

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime, timedelta

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.db import get_database
from app.core.errors import ValidationFailed
from app.core.models_base import utcnow
from app.modules.connectors.credentials import CredentialUnavailable, NotAuthorized
from app.modules.connectors.models import AuthKind, Connector
from app.modules.oauth import protocol
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.protocol import ClientCredentials, TokenFailure, Tokens, TokenStatus

logger = logging.getLogger(__name__)

EXPIRY_MARGIN = timedelta(seconds=60)
# A second renewal waits this long for the first one's lock (> the token timeout).
LOCK_TIMEOUT = "30s"


@asynccontextmanager
async def _unit() -> AsyncIterator[AsyncSession]:
    async with get_database().session_factory() as session, session.begin():
        yield session


# Tests hand in a unit on their own session (`tests/factories_oauth.py`).
open_unit: Callable[[], AbstractAsyncContextManager[AsyncSession]] = _unit


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def expiring(expires_at: datetime | None, now: datetime) -> bool:
    return expires_at is not None and expires_at - now <= EXPIRY_MARGIN


async def bearer_headers(connector: Connector) -> dict[str, str]:
    """The headers for a call with `connector` (kind `oauth`), renewed first when the
    token is about to expire and a refresh token is there."""
    assert connector.auth_kind == AuthKind.OAUTH
    if connector.secret_ref is None:
        raise NotAuthorized()
    if connector.refresh_token_ref is not None and expiring(connector.token_expires_at, utcnow()):
        return await renew(connector.org_id, connector.id, used=None)
    return bearer(_plain(connector.secret_ref))


async def renew(org_id: uuid.UUID, connector_id: uuid.UUID, *, used: str | None) -> dict[str, str]:
    """Renew the connector's token unless someone did meanwhile. `used` is the token a
    server refused (None: renew because it is about to expire)."""
    async with open_unit() as session:
        await session.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))
        connector = await session.scalar(
            select(Connector)
            .where(Connector.org_id == org_id, Connector.id == connector_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if connector is None or connector.secret_ref is None:
            raise NotAuthorized()
        current = _plain(connector.secret_ref)
        if used is not None:
            stale = current == used
        else:
            stale = expiring(connector.token_expires_at, utcnow())
        if not stale or connector.refresh_token_ref is None:
            return bearer(current)
        client = await session.get(OAuthClient, connector.oauth_client_id)
        assert client is not None and client.org_id == org_id
        refresh = protocol.refresh(credentials_of(client), _plain(connector.refresh_token_ref))
        try:
            tokens = await timed(connector.id, "refresh_token", refresh)
            store(connector, tokens, keep_refresh=True)
        except TokenFailure as failure:
            if failure.status != TokenStatus.INVALID_GRANT:
                raise CredentialUnavailable() from None
            forget(connector)
            disconnected = True
        else:
            disconnected = False
        await session.flush()
    if disconnected:  # committed: the dead tokens are gone for every worker
        raise NotAuthorized()
    return bearer(tokens.access_token)


def credentials_of(client: OAuthClient) -> ClientCredentials:
    secret = None
    if client.client_secret_ref is not None:
        secret = _plain(client.client_secret_ref)
    return ClientCredentials(
        client_id=client.client_id,
        secret=secret,
        token_auth=client.token_auth,
        token_endpoint=client.token_endpoint,
        revocation_endpoint=client.revocation_endpoint,
        resource=client.resource,
    )


def store(connector: Connector, tokens: Tokens, *, keep_refresh: bool) -> None:
    """The tokens on the connector, `enc:` (a token unfit for a header is an invalid
    answer: nothing is stored)."""
    try:
        access = secrets.encrypt(tokens.access_token)
        refresh = secrets.encrypt(tokens.refresh_token) if tokens.refresh_token else None
    except ValidationFailed:  # a value unfit for a header, or no key
        raise TokenFailure(TokenStatus.INVALID_RESPONSE) from None
    connector.secret_ref = access
    if refresh is not None or not keep_refresh:
        connector.refresh_token_ref = refresh
    connector.token_expires_at = utcnow() + tokens.expires_in if tokens.expires_in else None


def forget(connector: Connector) -> None:
    connector.secret_ref = None
    connector.refresh_token_ref = None
    connector.token_expires_at = None


async def timed[T](connector_id: uuid.UUID, grant: str, request: Awaitable[T]) -> T:
    started = time.monotonic()
    status = TokenStatus.OK
    try:
        return await request
    except TokenFailure as failure:
        status = failure.status
        raise
    finally:
        logger.info(
            "oauth.token_request",
            extra={
                "connector_id": str(connector_id),
                "grant": grant,
                "status": status.value,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )


def _plain(ref: str) -> str:
    try:
        return secrets.resolve(ref).get_secret_value()
    except secrets.SecretUnavailable:
        raise CredentialUnavailable() from None

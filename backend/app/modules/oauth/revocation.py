"""Revoking an OAuth connector's tokens at the provider (RFC 7009) when it is
disconnected or deleted: after the commit (nothing is revoked for a change that did
not happen), refresh token first (which ends the grant at most providers), then the
access token. Best effort: the tokens are gone from the database either way; a
provider without a revocation endpoint (GitHub has none for OAuth apps) or that fails
is noted in the log (`oauth.token_request`, grant `revocation`), never retried."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.db import after_commit
from app.modules.connectors.credentials import CredentialUnavailable
from app.modules.connectors.models import Connector
from app.modules.oauth import protocol
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.protocol import TokenFailure
from app.modules.oauth.tokens import credentials_of, timed

logger = logging.getLogger(__name__)


def schedule_revocation(session: AsyncSession, connector: Connector, client: OAuthClient) -> None:
    """Call before the tokens are dropped from `connector`; copies what it needs."""
    if client.revocation_endpoint is None or connector.secret_ref is None:
        return
    pending = [
        (connector.refresh_token_ref, "refresh_token"),
        (connector.secret_ref, "access_token"),
    ]
    try:
        credentials = credentials_of(client)
        tokens = [(secrets.resolve(ref).get_secret_value(), hint) for ref, hint in pending if ref]
    except (CredentialUnavailable, secrets.SecretUnavailable):
        return
    connector_id = connector.id

    async def revoke(_: AsyncSession) -> None:
        for token, hint in tokens:
            try:
                await timed(connector_id, "revocation", protocol.revoke(credentials, token, hint))
            except TokenFailure:
                pass  # logged by `timed`; the tokens are gone here anyway

    after_commit(session, revoke)

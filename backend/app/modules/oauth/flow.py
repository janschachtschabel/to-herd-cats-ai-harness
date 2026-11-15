"""Connecting and disconnecting an OAuth connector (plan M8 task 8): authorization code
with PKCE (RFC 7636, S256).

- `start` (who may manage the connector: `ai.manage` for a shared one, its owner with
  `ai.use` for a personal one): a fresh `state` (256 bits) and verifier; Postgres
  keeps the state's SHA-256, the verifier `enc:`, the login session and the redirect
  URI, for `FLOW_MINUTES`. The redirect URI is the configured public address
  (`HERD_PUBLIC_URL`) plus `CALLBACK_PATH`, never taken from the request; without
  that address, or with plain http other than localhost, there is no OAuth (422
  `connector.oauth_unconfigured`).
- `finish` (the callback, in the browser of the person who started): the flow the
  state names is deleted in the statement that finds it, only for the login session
  that started it and before it expires, so it is used once. The rights are checked
  again, the transaction committed, then the code exchanged (with the verifier, the
  same redirect URI and the resource) through the egress guard; the tokens are stored
  `enc:`. The answer is a fixed status for the page the browser goes to next
  (`Outcome`), never the provider's words.
- `disconnect`: the tokens dropped, revoked at the provider after the commit.
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from urllib.parse import urlencode, urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.access import Actor, actor_for
from app.core.config import get_settings
from app.core.errors import NotFound, Unauthorized, ValidationFailed
from app.core.models_base import utcnow
from app.modules.audit.recorder import record
from app.modules.auth.context import AuthContext
from app.modules.connectors.credentials import CredentialUnavailable
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope
from app.modules.connectors.repository import ConnectorRepository
from app.modules.connectors.service import ConnectorService, connector_not_found
from app.modules.oauth import protocol
from app.modules.oauth.models import OAuthClient, OAuthFlow
from app.modules.oauth.repository import ClientRepository, FlowRepository
from app.modules.oauth.revocation import schedule_revocation
from app.modules.oauth.tokens import credentials_of, forget, store, timed

CALLBACK_PATH = "/api/ai/oauth/callback"
DONE_PATH = "/ai/oauth/done"
FLOW_MINUTES = 10
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class Outcome(StrEnum):
    CONNECTED = "connected"
    DENIED = "denied"  # the person declined at the provider
    FAILED = "failed"  # the provider answered with an error, or the exchange failed
    INVALID = "invalid"  # unknown, used, expired or someone else's state; rights gone


@dataclass(frozen=True, slots=True)
class Finished:
    outcome: Outcome
    connector: Connector | None = None

    def location(self) -> str:
        """Where the browser goes next: a page of the app, same origin."""
        query = {"status": self.outcome.value}
        if self.connector is not None:
            query |= {"connector": str(self.connector.id), "scope": self.connector.scope}
        return f"{DONE_PATH}?{urlencode(query)}"


def redirect_uri() -> str:
    public = get_settings().public_url
    parts = urlsplit(public) if public else None
    if parts is None or (parts.scheme != "https" and parts.hostname not in _LOCAL_HOSTS):
        raise ValidationFailed(code="connector.oauth_unconfigured")
    return public.rstrip("/") + CALLBACK_PATH  # type: ignore[union-attr]


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


class FlowService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _oauth(
        self, actor: Actor, scope: ConnectorScope, connector_id: uuid.UUID
    ) -> tuple[ConnectorRepository, Connector]:
        repo = await ConnectorService(self.session).repo(actor, scope)
        connector = await repo.get(connector_id)
        if connector is None:
            raise connector_not_found()
        if connector.auth_kind != AuthKind.OAUTH:
            raise ValidationFailed(code="connector.not_oauth")
        return repo, connector

    async def _client(self, connector: Connector) -> OAuthClient:
        assert connector.oauth_client_id is not None
        client = await ClientRepository(self.session, connector.org_id).get(
            connector.oauth_client_id
        )
        assert client is not None  # the foreign key keeps it
        return client

    async def start(
        self,
        actor: Actor,
        session_id: uuid.UUID | None,
        scope: ConnectorScope,
        connector_id: uuid.UUID,
    ) -> str:
        _, connector = await self._oauth(actor, scope, connector_id)
        uri = redirect_uri()
        if session_id is None:
            raise Unauthorized(code="auth.session_invalid")
        client = await self._client(connector)
        state, verifier = protocol.new_state(), protocol.new_verifier()
        flows = FlowRepository(self.session, actor.org_id)
        now = utcnow()
        await flows.drop_expired(now)
        await flows.add(
            OAuthFlow(
                org_id=actor.org_id,
                connector_id=connector.id,
                session_id=session_id,
                state_hash=_hash(state),
                verifier_ref=secrets.encrypt(verifier),
                redirect_uri=uri,
                expires_at=now + timedelta(minutes=FLOW_MINUTES),
            )
        )
        return protocol.authorization_url(
            client.authorization_endpoint,
            client_id=client.client_id,
            redirect_uri=uri,
            state=state,
            verifier=verifier,
            scopes=client.scopes,
            resource=client.resource,
        )

    async def finish(
        self, auth: AuthContext | None, state: str | None, code: str | None, error: str | None
    ) -> Finished:
        if auth is None or auth.session_id is None or not state:
            return Finished(Outcome.INVALID)
        flows = FlowRepository(self.session, auth.org_id)
        flow = await flows.take(_hash(state), auth.session_id, utcnow())
        if flow is None:
            return Finished(Outcome.INVALID)
        actor = await actor_for(self.session, auth)
        scope = await self.session.scalar(
            select(Connector.scope).where(
                Connector.org_id == auth.org_id, Connector.id == flow.connector_id
            )
        )
        if scope is None:
            return Finished(Outcome.INVALID)
        try:
            repo, connector = await self._oauth(actor, ConnectorScope(scope), flow.connector_id)
        except (NotFound, ValidationFailed):
            return Finished(Outcome.INVALID)
        if error is not None or not code:
            await self.session.commit()  # the flow is used up either way
            return Finished(
                Outcome.DENIED if error == "access_denied" else Outcome.FAILED, connector
            )
        client = await self._client(connector)
        try:
            credentials = credentials_of(client)
            verifier = secrets.resolve(flow.verifier_ref).get_secret_value()
        except (CredentialUnavailable, secrets.SecretUnavailable):
            return Finished(Outcome.FAILED, connector)
        client_id = client.id
        await self.session.commit()  # nothing held while the provider answers
        exchange = protocol.exchange_code(
            credentials, code=code, verifier=verifier, redirect_uri=flow.redirect_uri
        )
        try:
            tokens = await timed(connector.id, "authorization_code", exchange)
            locked = await repo.get(connector.id, lock=True)
            if locked is None or locked.oauth_client_id != client_id:
                return Finished(Outcome.INVALID)
            store(locked, tokens, keep_refresh=False)
        except protocol.TokenFailure:
            return Finished(Outcome.FAILED, connector)
        locked.version += 1
        await self.session.flush()
        details = {"scope": locked.scope, "refresh_token": locked.refresh_token_ref is not None}
        await record(self.session, actor, "connector.connected", "connector", locked.id, details)
        return Finished(Outcome.CONNECTED, locked)

    async def disconnect(
        self, actor: Actor, scope: ConnectorScope, connector_id: uuid.UUID, version: int
    ) -> Connector:
        service = ConnectorService(self.session)
        repo, _ = await self._oauth(actor, scope, connector_id)
        connector = await service.current(repo, connector_id, version)
        schedule_revocation(self.session, connector, await self._client(connector))
        forget(connector)
        connector.version += 1
        await self.session.flush()
        details = {"scope": connector.scope}
        await record(
            self.session, actor, "connector.disconnected", "connector", connector.id, details
        )
        return connector

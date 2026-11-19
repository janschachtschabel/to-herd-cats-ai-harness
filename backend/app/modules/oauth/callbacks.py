"""Where an authorization server sends the browser back (plan M9 task 18, J13; ASVS 5.0
V10.2.2, RFC 9207 and the OAuth security BCP's mix-up defence).

Every OAuth app has a callback of its own, `/api/ai/oauth/{id}/callback`: a flow is
started with its app's, and a response is taken only at the callback its flow names, so
a response one authorization server sends cannot finish a flow begun with another. The
shared `/api/ai/oauth/callback` of earlier releases answers only for flows started with
it (they expire after `flow.FLOW_MINUTES`), never for a flow started since.

`iss` (RFC 9207): when the response carries one, or the app's server promised one
(`issuer_in_response`, from its metadata), it must equal the app's `issuer` exactly.
An app without a recorded issuer cannot judge a sent `iss`; its own callback is then
the protection (discovery records the issuer; an admin may enter it)."""

import uuid
from urllib.parse import urlsplit

from app.core.config import get_settings
from app.core.errors import ValidationFailed
from app.modules.oauth.models import OAuthClient, OAuthFlow

LEGACY_CALLBACK_PATH = "/api/ai/oauth/callback"
CALLBACK_PATH = "/api/ai/oauth/{client_id}/callback"
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def callback_path(client_id: uuid.UUID | None) -> str:
    """The app's own callback path; None: the shared one of earlier releases."""
    return LEGACY_CALLBACK_PATH if client_id is None else CALLBACK_PATH.format(client_id=client_id)


def _public() -> str | None:
    public = get_settings().public_url
    parts = urlsplit(public) if public else None
    if parts is None or (parts.scheme != "https" and parts.hostname not in _LOCAL_HOSTS):
        return None
    return public.rstrip("/")  # type: ignore[union-attr]


def callback_url(client_id: uuid.UUID) -> str | None:
    """What to register at the provider; None without a usable public address."""
    public = _public()
    return None if public is None else public + callback_path(client_id)


def redirect_uri(client_id: uuid.UUID) -> str:
    """The redirect URI of a new flow: the configured public address (never the
    request's) plus the app's callback; 422 without a usable address."""
    uri = callback_url(client_id)
    if uri is None:
        raise ValidationFailed(code="connector.oauth_unconfigured")
    return uri


def arrived_where_sent(flow: OAuthFlow, client_id: uuid.UUID | None) -> bool:
    """Whether the response came to the callback the flow was started with."""
    return urlsplit(flow.redirect_uri).path == callback_path(client_id)


def issuer_matches(client: OAuthClient, iss: str | None) -> bool:
    """RFC 9207 2.4: a sent `iss` is the app's issuer (simple string comparison); a
    server that promised `iss` must send it."""
    if iss is None:
        return not client.issuer_in_response
    return client.issuer is None or iss == client.issuer

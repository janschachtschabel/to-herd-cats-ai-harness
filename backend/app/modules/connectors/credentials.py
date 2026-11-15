"""What a connector puts on an outbound request: one header carrying its secret. The
plaintext is formed here (or, for OAuth, in `modules/oauth/tokens.py`), at the moment
of the call, and goes nowhere but into that header (never into a prompt, tool
arguments, the journal, logs or audit)."""

from app.core import secrets
from app.modules.connectors.models import AuthKind, Connector


class CredentialUnavailable(Exception):  # noqa: N818 (a state, not an error class name)
    """The connector's secret cannot be resolved (unset variable, rotated key), or an
    OAuth provider could not renew the token just now."""

    def __init__(self) -> None:
        super().__init__("credential unavailable")


class NotAuthorized(CredentialUnavailable):
    """An OAuth connector without tokens (never connected, disconnected, or the
    provider refused its refresh token): someone connects it (again)."""


def headers_for(connector: Connector) -> dict[str, str]:
    """For the fixed kinds (`bearer`, `header`)."""
    assert connector.auth_kind != AuthKind.OAUTH and connector.secret_ref is not None
    try:
        value = secrets.resolve(connector.secret_ref).get_secret_value()
    except secrets.SecretUnavailable:
        raise CredentialUnavailable() from None
    if connector.auth_kind == AuthKind.HEADER:
        assert connector.header_name is not None
        return {connector.header_name: value}
    return {"Authorization": f"Bearer {value}"}


async def credential_headers(connector: Connector) -> dict[str, str]:
    """For any kind; an OAuth token about to expire is renewed first."""
    if connector.auth_kind == AuthKind.OAUTH:
        from app.modules.oauth.tokens import bearer_headers  # noqa: PLC0415 (oauth uses us)

        return await bearer_headers(connector)
    return headers_for(connector)

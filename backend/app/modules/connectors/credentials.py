"""What a connector puts on an outbound request: one header carrying its secret. The
plaintext is formed here, at the moment of the call, and goes nowhere but into that
header (never into a prompt, tool arguments, the journal, logs or audit)."""

from app.core import secrets
from app.modules.connectors.models import AuthKind, Connector


class CredentialUnavailable(Exception):  # noqa: N818 (a state, not an error class name)
    """The connector's secret cannot be resolved (unset variable, rotated key)."""

    def __init__(self) -> None:
        super().__init__("credential unavailable")


def headers_for(connector: Connector) -> dict[str, str]:
    try:
        value = secrets.resolve(connector.secret_ref).get_secret_value()
    except secrets.SecretUnavailable:
        raise CredentialUnavailable() from None
    if connector.auth_kind == AuthKind.HEADER:
        assert connector.header_name is not None
        return {connector.header_name: value}
    return {"Authorization": f"Bearer {value}"}

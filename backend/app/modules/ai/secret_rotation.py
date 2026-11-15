"""Re-encrypting stored secrets under the current `HERD_SECRET_KEY` (docs/KI.md):
with the old key in `HERD_SECRET_KEY_PREVIOUS`, every `enc:` reference (AI
connections; connectors, shared and personal, with their OAuth access and refresh
tokens; OAuth client secrets; open OAuth flows' verifiers) is rotated in one
transaction; if any cannot be decrypted, nothing changes. The values are never shown;
a failure names only the table and the row's id."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.modules.ai.repository import encrypted_connections
from app.modules.connectors.repository import encrypted_connectors
from app.modules.oauth.repository import all_flows, encrypted_clients


class RotationFailed(Exception):  # noqa: N818
    def __init__(self, table: str, row_id: uuid.UUID) -> None:
        self.table = table
        self.row_id = row_id
        super().__init__(f"{table} {row_id}: secret cannot be decrypted")


def _rotated(table: str, row_id: uuid.UUID, ref: str) -> str:
    try:
        return secrets.rotate(ref)
    except secrets.SecretUnavailable:
        raise RotationFailed(table, row_id) from None


async def rotate_secrets(session: AsyncSession) -> int:
    """The number of references rotated; the caller commits."""
    connections = await encrypted_connections(session)
    for connection in connections:
        assert connection.secret_ref is not None
        connection.secret_ref = _rotated("ai_connection", connection.id, connection.secret_ref)
    count = len(connections)
    for connector in await encrypted_connectors(session):
        for name in ("secret_ref", "refresh_token_ref"):
            ref = getattr(connector, name)
            if ref is not None and ref.startswith(secrets.ENC_PREFIX):
                setattr(connector, name, _rotated("connector", connector.id, ref))
                count += 1
    for client in await encrypted_clients(session):
        assert client.client_secret_ref is not None
        client.client_secret_ref = _rotated("oauth_client", client.id, client.client_secret_ref)
        count += 1
    for flow in await all_flows(session):
        flow.verifier_ref = _rotated("oauth_flow", flow.id, flow.verifier_ref)
        count += 1
    await session.flush()
    return count

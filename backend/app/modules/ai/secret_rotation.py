"""Re-encrypting stored secrets under the current `HERD_SECRET_KEY` (docs/KI.md):
with the old key in `HERD_SECRET_KEY_PREVIOUS`, every `enc:` reference is rotated in
one transaction; if any cannot be decrypted, nothing changes. The values are never
shown; a failure names only the connection's id."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.modules.ai.repository import encrypted_connections


class RotationFailed(Exception):  # noqa: N818
    def __init__(self, connection_id: uuid.UUID) -> None:
        self.connection_id = connection_id
        super().__init__(f"connection {connection_id}: secret cannot be decrypted")


async def rotate_secrets(session: AsyncSession) -> int:
    """The number of references rotated; the caller commits."""
    connections = await encrypted_connections(session)
    for connection in connections:
        assert connection.secret_ref is not None
        try:
            connection.secret_ref = secrets.rotate(connection.secret_ref)
        except secrets.SecretUnavailable:
            raise RotationFailed(connection.id) from None
    await session.flush()
    return len(connections)

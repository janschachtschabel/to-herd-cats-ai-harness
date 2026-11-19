"""A secret goes only where it was given for (module review M8 1, finding 4).

A person connects their own connector for one external server at one address (for
OAuth: through one client's endpoints). When someone with `ai.manage` gives the
server another origin (`moved_origin`: scheme, host or port as `origins.origin_of`
spells them; the path does not count, since the same origin is the same party, which
already holds the secret), or the client another authorization, token or revocation
endpoint (`MOVING_ENDPOINTS`), the connectors that were connected for the old place
are disconnected in the same transaction (`disconnect`): a personal one is deleted
(the person sees "not connected" with the new address and connects again,
knowingly), a shared OAuth one of the client loses its tokens unless the change keeps
it explicitly. OAuth tokens are revoked at the old provider after the commit
(`oauth/revocation.py`, best effort). The shared connector of a moved server is the
server's to detach (`mcp_servers`).

The rule holds for every purpose (plan M10 decision 18): a calendar app's new endpoints
disconnect the calendar accesses through it exactly so (they are personal; managed with
`calendar.manage`, `oauth/clients.py`). A server's connectors are `mcp` ones; a
client's are of the client's purpose (the foreign key on `(oauth_client_id, purpose)`).
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.connectors.models import Connector, ConnectorScope, Purpose
from app.modules.connectors.origins import same_origin
from app.modules.connectors.repository import bound_connectors, delete_connectors
from app.modules.oauth.models import OAuthClient
from app.modules.oauth.repository import ClientRepository
from app.modules.oauth.revocation import schedule_revocation
from app.modules.oauth.tokens import forget

MOVING_ENDPOINTS = ("authorization_endpoint", "token_endpoint", "revocation_endpoint")


@dataclass(frozen=True, slots=True)
class Disconnected:
    personal: int = 0
    shared: int = 0


def moved_origin(before: str, after: str) -> bool:
    """Whether the server's URL names another origin (`origins.origin_of`, the spelling
    a calendar access records, too). An unchanged URL never moves; one without a
    spelling cannot be shown to be the same origin, so it counts as moved."""
    return before != after and not same_origin(before, after)


async def disconnect_server(
    session: AsyncSession, org_id: uuid.UUID, server_id: uuid.UUID
) -> Disconnected:
    """Every personal connector bound to the moved server: revoked (OAuth, at the
    provider it was connected with) and deleted."""
    bound = await bound_connectors(session, org_id, server_id=server_id)
    for connector in bound:
        if connector.oauth_client_id is not None:
            clients = ClientRepository(session, org_id, Purpose(connector.purpose))
            client = await clients.get(connector.oauth_client_id)
            if client is not None:
                schedule_revocation(session, connector, client)
    await delete_connectors(session, bound)
    return Disconnected(personal=len(bound))


async def disconnect_client(
    session: AsyncSession, client: OAuthClient, *, keep_shared: bool
) -> Disconnected:
    """Before the client's endpoints change (it still names the old ones): every
    personal connector through it revoked and deleted; every shared one revoked and
    without tokens, unless `keep_shared`."""
    bound = await bound_connectors(session, client.org_id, client_id=client.id)
    personal: list[Connector] = []
    shared = 0
    for connector in bound:
        if connector.scope == ConnectorScope.PERSONAL:
            schedule_revocation(session, connector, client)
            personal.append(connector)
        elif not keep_shared and connector.secret_ref is not None:
            schedule_revocation(session, connector, client)
            forget(connector)
            connector.version += 1
            shared += 1
    await delete_connectors(session, personal)
    return Disconnected(personal=len(personal), shared=shared)

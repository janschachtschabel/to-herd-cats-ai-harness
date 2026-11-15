"""Where a call to an external MCP server goes and with which credential, copied out
of the rows (no session is held while the server answers).

The credential is the server's shared connector, or, for a server that acts with each
person's own connector, the connector of the person the call is made for. Its secret
is resolved here, at the moment of the call, into the endpoint's headers and nowhere
else. A server on a host the operator lists as private (`HERD_MCP_ALLOWED_HOSTS`) is
dialled directly, past an egress proxy meant for the outside.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.egress import EgressRules
from app.core.egress_allowance import PrivateAllowance, parse_allowance
from app.mcp.client import RULES, Endpoint
from app.modules.ai.provider import egress_proxy
from app.modules.connectors import credentials
from app.modules.connectors.models import Connector
from app.modules.connectors.repository import ConnectorRepository
from app.modules.mcp_servers.errors import CredentialUnavailable, NotConnected
from app.modules.mcp_servers.models import ConnectorUse, McpServer


async def connector_for(
    session: AsyncSession, server: McpServer, person_id: uuid.UUID | None
) -> Connector | None:
    """The connector a call for `person_id` uses (None: the server needs none, or the
    person has none; `endpoint_for` decides whether that is allowed)."""
    if server.connector_scope == ConnectorUse.SHARED:
        assert server.connector_id is not None
        return await ConnectorRepository(session, server.org_id, None).get(server.connector_id)
    if server.connector_scope == ConnectorUse.PERSONAL and person_id is not None:
        return await ConnectorRepository(session, server.org_id, person_id).for_server(server.id)
    return None


async def endpoint_for(
    session: AsyncSession, server: McpServer, person_id: uuid.UUID | None, *, strict: bool
) -> Endpoint:
    """With `strict`, a personal server without the person's connector is
    `NotConnected` (a call); without, it is reached without credential (an admin
    reading the tool list of a server that lists tools to anyone)."""
    connector = await connector_for(session, server, person_id)
    if connector is None and strict and server.connector_scope == ConnectorUse.PERSONAL:
        raise NotConnected()
    headers: dict[str, str] = {}
    if connector is not None:
        try:
            headers = credentials.headers_for(connector)
        except credentials.CredentialUnavailable:
            raise CredentialUnavailable() from None
    allowance = private_allowance()
    proxy = None if allowance.covers(server.url) else egress_proxy()  # in-house: direct
    return Endpoint(server.url, headers, proxy, allowance.rules(RULES))


def private_allowance() -> PrivateAllowance:
    """The operator's private hosts for MCP servers (`HERD_MCP_ALLOWED_HOSTS`)."""
    return parse_allowance(get_settings().mcp_allowed_hosts)


def server_rules() -> EgressRules:
    """The egress rules of a server's URL and calls: https, public addresses, and the
    private hosts the operator lists."""
    return private_allowance().rules(RULES)

"""The metric of OAuth renewals (plan M8 task 13): every refresh-token request to an
authorization server, by its fixed status (`protocol.TokenStatus`: ok, invalid_grant,
rejected, blocked, timeout, unreachable, redirect, server_error, invalid_response).
Never a connector, a client or a provider as a label. API pods renew while reading a
server's tools, workers while calling them in runs."""

from prometheus_client import Counter

from app.core.metrics import REGISTRY

OAUTH_REFRESHES = Counter(
    "herd_oauth_refreshes_total",
    "Renewals of OAuth connectors' access tokens, by the authorization server's answer.",
    ["status"],
    registry=REGISTRY,
)

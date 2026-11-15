"""The metric of OIDC sign-ins (plan M9 task 4): every callback by its outcome, a fixed
word (`login`, `link`, `signup`, `profile_link`, or a refusal's code without the
`oidc.` prefix: `link_refused`, `signup_closed`, `domain_not_allowed`,
`email_unverified`, `account_inactive`, `flow_invalid`, `denied`, `rate_limited`,
`unavailable`, `identity_taken`, `provider_unreachable`, `provider_error`,
`issuer_mismatch`, `id_token_invalid`). Never a provider, a person or an address as a
label. `HerdOidcFailing` alerts when the provider's share of failures
(`PROVIDER_FAILURES`) is above half over 15 minutes."""

from prometheus_client import Counter

from app.core.metrics import REGISTRY

PROVIDER_FAILURES = frozenset(
    {"provider_unreachable", "provider_error", "issuer_mismatch", "id_token_invalid"}
)

OIDC_LOGINS = Counter(
    "herd_oidc_logins_total",
    "OIDC sign-in callbacks, by outcome (a fixed word or refusal code).",
    ["outcome"],
    registry=REGISTRY,
)


def count_outcome(outcome: str) -> None:
    OIDC_LOGINS.labels(outcome=outcome).inc()

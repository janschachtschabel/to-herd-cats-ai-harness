"""What a provider's kind means (plan M9 decisions 12, 14 and 15).

Google (checked against Google's OpenID Connect reference and its discovery document,
https://developers.google.com/identity/openid-connect/reference and
https://accounts.google.com/.well-known/openid-configuration, on 2026-11-15): the
issuer is `https://accounts.google.com`, and ID tokens of older integrations carry
`accounts.google.com` as `iss`, so both are accepted; the scopes are
`openid email profile`; ID tokens are signed RS256; `hd` names the Workspace or Cloud
organisation of the account and must be checked to restrict access to a domain;
`prompt=select_account` lets the person pick an account; the `hd` parameter of the
authentication request only streamlines the choice (sent when exactly one domain other
than gmail.com is allowed), the claim is what counts. Google advises `sub`, not the
email, as the key of the account (here `user_identity`).

A generic provider names its own issuer and scopes (`openid` among them).
"""

import re
from typing import Final

from app.modules.oidc.admission import GMAIL, ProviderRules
from app.modules.oidc.models import OidcProvider, ProviderKind

GOOGLE_ISSUER: Final = "https://accounts.google.com"
GOOGLE_ISSUERS: Final = frozenset({GOOGLE_ISSUER, "accounts.google.com"})
GOOGLE_SCOPES: Final = "openid email profile"
GOOGLE_NAME: Final = "Google"
_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_DOMAIN = re.compile(rf"{_LABEL}(?:\.{_LABEL})+")


def issuers_of(provider: OidcProvider) -> frozenset[str]:
    if provider.kind == ProviderKind.GOOGLE:
        return GOOGLE_ISSUERS
    return frozenset({provider.issuer})


def rules_of(provider: OidcProvider) -> ProviderRules:
    return ProviderRules(
        kind=ProviderKind(provider.kind),
        trust_email=provider.trust_email and provider.kind == ProviderKind.GENERIC,
        allow_signup=provider.allow_signup,
        allowed_domains=frozenset(provider.allowed_domains),
    )


def extra_parameters(provider: OidcProvider) -> dict[str, str]:
    """What the authentication request adds for the provider's kind."""
    if provider.kind != ProviderKind.GOOGLE:
        return {}
    extra = {"prompt": "select_account"}
    domains = provider.allowed_domains
    if len(domains) == 1 and domains[0] != GMAIL:
        extra["hd"] = domains[0]
    return extra


def normalize_domain(raw: str) -> str:
    """A domain as the allow-list keeps it: lower case, exact; ValueError for anything
    else (a trailing dot, a wildcard, an address)."""
    domain = raw.strip().lower()
    if len(domain) > 253 or _DOMAIN.fullmatch(domain) is None:
        raise ValueError("not a domain")
    return domain

"""Who gets in through OIDC, and as whom (plan M9 decisions 13 and 14). Pure: the
flow looks up the person by subject and by email, this decides.

1. A known subject (`user_identity`) logs its person in; a self-registered person
   still awaiting an admin's approval is refused with `oidc.account_pending`, a
   deactivated (or rejected) one with `oidc.account_inactive`.
2. Otherwise the email must be present and verified (`oidc.email_unverified`).
3. An active account with that email is linked only where the provider is
   authoritative for the address: Google for `@gmail.com` or when `hd` is the
   address's domain; a generic provider only with `trust_email`. Otherwise
   `oidc.link_refused` (sign in with the password, then link in the profile). An
   account awaiting approval or deactivated is refused as in 1, and not linked.
4. Without an account: self-registration if the provider allows it and lists
   domains, and a generic provider is trusted for addresses (`trust_email`, as for
   linking: module review M9a, N4); `oidc.signup_closed` otherwise. For an address
   whose domain is listed
   exactly (no subdomains, no trailing dot); at Google a domain other than
   `gmail.com` also needs `hd` equal to it (`oidc.domain_not_allowed`). The new
   account waits for an admin's approval (Jan's answer J2: nobody gets in without
   it; `accounts.py`).

`SIGNUP_GETS_NO_AI` is question J2: a self-registered person gets an own AI
assignment "no AI" until an admin decides (costs and data leaving only by decision).
Set it to False to let the organisation's standard assignment apply at once.
"""

import uuid
from dataclasses import dataclass
from typing import Final

from app.modules.oidc.id_token import IdClaims
from app.modules.oidc.models import ProviderKind

SIGNUP_GETS_NO_AI: Final = True  # J2: "ausdrücklich keine KI" for self-registered people
GMAIL: Final = "gmail.com"
MAX_NAME_CHARS = 120


@dataclass(frozen=True, slots=True)
class ProviderRules:
    kind: ProviderKind
    trust_email: bool
    allow_signup: bool
    allowed_domains: frozenset[str]


@dataclass(frozen=True, slots=True)
class ExistingUser:
    id: uuid.UUID
    active: bool
    pending: bool = False  # self-registered and not yet approved (`awaiting_approval_since`)


@dataclass(frozen=True, slots=True)
class Login:
    user_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class Link:
    user_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class Signup:
    email: str
    name: str


@dataclass(frozen=True, slots=True)
class Refuse:
    code: str


type Admission = Login | Link | Signup | Refuse


def domain_of(email: str) -> str:
    return email.rpartition("@")[2]


def authoritative(rules: ProviderRules, email: str, hd: str | None) -> bool:
    """Whether the provider vouches for this address (not merely that it was verified
    once): Google for its own mail and for Workspace domains it manages."""
    if rules.kind == ProviderKind.GOOGLE:
        domain = domain_of(email)
        return domain == GMAIL or (hd is not None and hd.lower() == domain)
    return rules.trust_email


def _usable(user: ExistingUser) -> Refuse | None:
    """Why this account may not sign in (None: it may)."""
    if user.pending:
        return Refuse("oidc.account_pending")
    return None if user.active else Refuse("oidc.account_inactive")


def decide(
    rules: ProviderRules,
    claims: IdClaims,
    by_subject: ExistingUser | None,
    by_email: ExistingUser | None,
) -> Admission:
    if by_subject is not None:
        return _usable(by_subject) or Login(by_subject.id)
    email = claims.email
    if not email or not claims.email_verified:
        return Refuse("oidc.email_unverified")
    if by_email is not None:
        if not authoritative(rules, email, claims.hd):
            return Refuse("oidc.link_refused")
        return _usable(by_email) or Link(by_email.id)
    if not rules.allow_signup or not rules.allowed_domains:
        return Refuse("oidc.signup_closed")
    if rules.kind == ProviderKind.GENERIC and not rules.trust_email:
        return Refuse("oidc.signup_closed")  # it does not vouch for the address
    domain = domain_of(email)
    if domain not in rules.allowed_domains:
        return Refuse("oidc.domain_not_allowed")
    if rules.kind == ProviderKind.GOOGLE and not authoritative(rules, email, claims.hd):
        return Refuse("oidc.domain_not_allowed")
    name = (claims.name or email.partition("@")[0])[:MAX_NAME_CHARS]
    return Signup(email, name)

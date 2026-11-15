"""Who gets in through OIDC (plan M9 decisions 13 and 14): the admission matrix."""

import uuid
from dataclasses import replace

import pytest

from app.modules.oidc.admission import (
    ExistingUser,
    Link,
    Login,
    ProviderRules,
    Refuse,
    Signup,
    decide,
)
from app.modules.oidc.id_token import IdClaims
from app.modules.oidc.models import ProviderKind

ANNA = uuid.UUID(int=1)
ACTIVE = ExistingUser(ANNA, active=True)
INACTIVE = ExistingUser(ANNA, active=False)
PENDING = ExistingUser(ANNA, active=False, pending=True)  # self-registered, not yet approved

GOOGLE = ProviderRules(
    ProviderKind.GOOGLE, trust_email=False, allow_signup=False, allowed_domains=frozenset()
)
GENERIC = replace(GOOGLE, kind=ProviderKind.GENERIC)
GOOGLE_SIGNUP = replace(GOOGLE, allow_signup=True, allowed_domains=frozenset({"example.com"}))
GENERIC_SIGNUP = replace(GENERIC, allow_signup=True, allowed_domains=frozenset({"example.com"}))


def claims(
    email: str | None = "anna@example.com",
    *,
    verified: bool = True,
    hd: str | None = None,
    name: str | None = "Anna",
) -> IdClaims:
    return IdClaims(sub="s1", email=email, email_verified=verified, hd=hd, name=name, locale=None)


# (case, rules, claims, by_subject, by_email, expected)
MATRIX = [
    ("known subject logs in", GOOGLE, claims(verified=False), ACTIVE, None, Login(ANNA)),
    ("known subject, inactive", GOOGLE, claims(), INACTIVE, None, Refuse("oidc.account_inactive")),
    ("known subject, pending", GOOGLE, claims(), PENDING, None, Refuse("oidc.account_pending")),
    (
        "email pending account",
        GOOGLE,
        claims(hd="example.com"),
        None,
        PENDING,
        Refuse("oidc.account_pending"),
    ),
    (
        "untrusted email of a pending account refuses link",
        GOOGLE,
        claims(),
        None,
        PENDING,
        Refuse("oidc.link_refused"),
    ),
    ("google gmail links", GOOGLE, claims("anna@gmail.com"), None, ACTIVE, Link(ANNA)),
    ("google hd links", GOOGLE, claims(hd="example.com"), None, ACTIVE, Link(ANNA)),
    ("google without hd refuses link", GOOGLE, claims(), None, ACTIVE, Refuse("oidc.link_refused")),
    (
        "google other hd refuses link",
        GOOGLE,
        claims(hd="other.com"),
        None,
        ACTIVE,
        Refuse("oidc.link_refused"),
    ),
    (
        "unverified email refuses link",
        GOOGLE,
        claims("anna@gmail.com", verified=False),
        None,
        ACTIVE,
        Refuse("oidc.email_unverified"),
    ),
    (
        "email inactive account",
        GOOGLE,
        claims(hd="example.com"),
        None,
        INACTIVE,
        Refuse("oidc.account_inactive"),
    ),
    (
        "generic without trust refuses link",
        GENERIC,
        claims(),
        None,
        ACTIVE,
        Refuse("oidc.link_refused"),
    ),
    (
        "generic with trust links",
        replace(GENERIC, trust_email=True),
        claims(),
        None,
        ACTIVE,
        Link(ANNA),
    ),
    ("no email at all", GOOGLE_SIGNUP, claims(None), None, None, Refuse("oidc.email_unverified")),
    ("signup closed", GOOGLE, claims(hd="example.com"), None, None, Refuse("oidc.signup_closed")),
    (
        "signup switch without domains",
        replace(GOOGLE, allow_signup=True),
        claims(hd="example.com"),
        None,
        None,
        Refuse("oidc.signup_closed"),
    ),
    (
        "domains without the switch",
        replace(GOOGLE, allowed_domains=frozenset({"example.com"})),
        claims(hd="example.com"),
        None,
        None,
        Refuse("oidc.signup_closed"),
    ),
    (
        "google signup with hd",
        GOOGLE_SIGNUP,
        claims(hd="example.com"),
        None,
        None,
        Signup("anna@example.com", "Anna"),
    ),
    (
        "google signup case-insensitive email",
        GOOGLE_SIGNUP,
        claims("anna@example.com", hd="example.com"),
        None,
        None,
        Signup("anna@example.com", "Anna"),
    ),
    (
        "google signup without hd",
        GOOGLE_SIGNUP,
        claims(),
        None,
        None,
        Refuse("oidc.domain_not_allowed"),
    ),
    (
        "google signup other hd",
        GOOGLE_SIGNUP,
        claims(hd="evil.com"),
        None,
        None,
        Refuse("oidc.domain_not_allowed"),
    ),
    (
        "subdomain refused",
        GOOGLE_SIGNUP,
        claims("a@sub.example.com", hd="sub.example.com"),
        None,
        None,
        Refuse("oidc.domain_not_allowed"),
    ),
    (
        "trailing dot refused",
        GOOGLE_SIGNUP,
        claims("a@example.com.", hd="example.com."),
        None,
        None,
        Refuse("oidc.domain_not_allowed"),
    ),
    (
        "gmail not listed",
        GOOGLE_SIGNUP,
        claims("a@gmail.com"),
        None,
        None,
        Refuse("oidc.domain_not_allowed"),
    ),
    (
        "gmail listed",
        replace(GOOGLE_SIGNUP, allowed_domains=frozenset({"gmail.com"})),
        claims("a@gmail.com"),
        None,
        None,
        Signup("a@gmail.com", "Anna"),
    ),
    (
        "unverified signup",
        GOOGLE_SIGNUP,
        claims(hd="example.com", verified=False),
        None,
        None,
        Refuse("oidc.email_unverified"),
    ),
    (
        "generic signup by domain",
        GENERIC_SIGNUP,
        claims(),
        None,
        None,
        Signup("anna@example.com", "Anna"),
    ),
    (
        "generic signup other domain",
        GENERIC_SIGNUP,
        claims("a@other.com"),
        None,
        None,
        Refuse("oidc.domain_not_allowed"),
    ),
    (
        "signup name from the address",
        GENERIC_SIGNUP,
        claims(name=None),
        None,
        None,
        Signup("anna@example.com", "anna"),
    ),
]


@pytest.mark.parametrize(
    ("rules", "id_claims", "by_subject", "by_email", "expected"),
    [case[1:] for case in MATRIX],
    ids=[case[0] for case in MATRIX],
)
def test_admission_matrix(
    rules: ProviderRules,
    id_claims: IdClaims,
    by_subject: ExistingUser | None,
    by_email: ExistingUser | None,
    expected: object,
) -> None:
    assert decide(rules, id_claims, by_subject, by_email) == expected


def test_claims_from_mixed_case_mail_are_lower_case_already() -> None:
    """`IdClaims.email` is lower case (`id_token._claims`); `Example.COM` in a token
    therefore meets an allowed `example.com`."""
    signup = decide(GOOGLE_SIGNUP, claims("anna@example.com", hd="Example.COM"), None, None)
    assert signup == Signup("anna@example.com", "Anna")

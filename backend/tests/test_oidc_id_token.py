"""ID token verification (plan M9 decision 12): RS256/ES256 only, `iss` exact, `aud`
holds the client, `azp` with several audiences, times with 60 s leeway, `nonce`."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.oidc.id_token import IdTokenInvalid, verify_id_token
from tests.support.oidc_keys import SigningKey, claims_for, jwks

ISSUER = "https://idp.test"
CLIENT = "herd-client"
NONCE = "nonce-1"
NOW = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
KEY = SigningKey("k1")
OTHER = SigningKey("k2")


def _claims(**extra: Any) -> dict[str, Any]:
    fixed = {"issuer": ISSUER, "client_id": CLIENT, "nonce": NONCE}
    claims = claims_for(**fixed, now=NOW.timestamp())
    for name, value in extra.items():
        if value is None:
            claims.pop(name, None)
        else:
            claims[name] = value
    return claims


def _verify(raw: str, *, keys: dict[str, Any] | None = None) -> Any:
    return verify_id_token(
        raw,
        jwks=keys or jwks(KEY),
        issuers=frozenset({ISSUER}),
        client_id=CLIENT,
        nonce=NONCE,
        now=NOW,
    )


def test_a_good_token_gives_its_claims() -> None:
    claims = _verify(KEY.sign(_claims(hd="example.com", email="Anna@Example.com")))
    assert claims.sub == "1234567890"
    assert claims.email == "anna@example.com"
    assert claims.email_verified is True
    assert claims.hd == "example.com"
    assert claims.name == "Anna Beispiel"


def test_es256_is_accepted_and_a_string_true_counts_as_verified() -> None:
    key = SigningKey("ec", alg="ES256")
    claims = _verify(key.sign(_claims(email_verified="true")), keys=jwks(key))
    assert claims.email_verified is True


def test_a_token_within_the_leeway_is_accepted() -> None:
    late = NOW.timestamp() - 3600 - 50
    _verify(KEY.sign(_claims(iat=int(late), exp=int(late) + 3600)))


CASES: dict[str, tuple[Callable[[], str], str]] = {
    "signature": (lambda: OTHER.sign(_claims(), kid="k1"), "signature"),
    "alg_none": (lambda: KEY.sign_none(_claims()), "alg"),
    "alg_hs256_public_key": (lambda: KEY.sign_hs256_with_public_key(_claims()), "alg"),
    "iss": (lambda: KEY.sign(_claims(iss="https://evil.test")), "iss"),
    "aud": (lambda: KEY.sign(_claims(aud="someone-else")), "aud"),
    "azp_other": (lambda: KEY.sign(_claims(aud=[CLIENT, "other"], azp="other")), "azp"),
    "azp_missing": (lambda: KEY.sign(_claims(aud=[CLIENT, "other"])), "azp"),
    "expired": (lambda: KEY.sign(_claims(exp=int(NOW.timestamp()) - 61)), "expired"),
    "iat_future": (lambda: KEY.sign(_claims(iat=int(NOW.timestamp()) + 120)), "not_yet_valid"),
    "nbf_future": (lambda: KEY.sign(_claims(nbf=int(NOW.timestamp()) + 120)), "not_yet_valid"),
    "nonce_other": (lambda: KEY.sign(_claims(nonce="other-nonce")), "nonce"),
    "nonce_missing": (lambda: KEY.sign(_claims(nonce=None)), "nonce"),
    "kid_unknown": (lambda: KEY.sign(_claims(), kid="k9"), "kid_unknown"),
    "garbage": (lambda: "not.a.token", "malformed"),
    "sub_empty": (lambda: KEY.sign(_claims(sub="")), "malformed"),
    "exp_missing": (lambda: KEY.sign(_claims(exp=None)), "malformed"),
}


@pytest.mark.parametrize("case", sorted(CASES))
def test_verify_id_token_refuses(case: str) -> None:
    make, reason = CASES[case]
    with pytest.raises(IdTokenInvalid) as refused:
        _verify(make())
    assert refused.value.reason == reason


def test_a_key_of_the_wrong_type_is_unknown() -> None:
    """An RS256 token whose `kid` names an EC key finds no usable key."""
    ec_key = SigningKey("k1", alg="ES256")
    with pytest.raises(IdTokenInvalid) as refused:
        _verify(KEY.sign(_claims()), keys=jwks(ec_key))
    assert refused.value.reason == "kid_unknown"

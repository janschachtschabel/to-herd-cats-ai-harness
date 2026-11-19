"""TOTP (RFC 6238) on HOTP (RFC 4226), with the RFCs' own test vectors."""

import base64
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlsplit

import pytest

from app.modules.totp import codes

# RFC 4226, appendix D: secret "12345678901234567890", counters 0 to 9.
HOTP_VECTORS = [
    "755224", "287082", "359152", "969429", "338314",
    "254676", "287922", "162583", "399871", "520489",
]  # fmt: skip

SEEDS = {
    "sha1": b"12345678901234567890",
    "sha256": b"12345678901234567890123456789012",
    "sha512": b"1234567890123456789012345678901234567890123456789012345678901234",
}
# RFC 6238, appendix B: time, then the 8-digit TOTP for SHA-1, SHA-256, SHA-512.
TOTP_VECTORS = [
    (59, "94287082", "46119246", "90693936"),
    (1111111109, "07081804", "68084774", "25091201"),
    (1111111111, "14050471", "67062674", "99943326"),
    (1234567890, "89005924", "91819424", "93441116"),
    (2000000000, "69279037", "90698825", "38618901"),
    (20000000000, "65353130", "77737706", "47863826"),
]


@pytest.mark.parametrize(("counter", "expected"), list(enumerate(HOTP_VECTORS)))
def test_hotp_matches_rfc_4226(counter: int, expected: str) -> None:
    assert codes.hotp(SEEDS["sha1"], counter) == expected


@pytest.mark.parametrize(("at", "sha1", "sha256", "sha512"), TOTP_VECTORS)
def test_totp_matches_rfc_6238(at: int, sha1: str, sha256: str, sha512: str) -> None:
    for algorithm, expected in (("sha1", sha1), ("sha256", sha256), ("sha512", sha512)):
        code = codes.hotp(SEEDS[algorithm], codes.step_at(at), digits=8, algorithm=algorithm)
        assert code == expected, algorithm


def test_a_step_is_thirty_seconds() -> None:
    assert codes.step_at(0) == codes.step_at(29) == 0
    assert codes.step_at(30) == 1
    assert codes.step_at(datetime(2026, 11, 16, 12, 0, 59, tzinfo=UTC).timestamp()) == (
        int(datetime(2026, 11, 16, 12, 0, 30, tzinfo=UTC).timestamp()) // 30
    )


def _key(secret: str) -> bytes:
    return base64.b32decode(secret)


def test_the_current_step_and_one_on_either_side_match() -> None:
    secret = codes.new_secret()
    now = 1_800_000_000
    step = codes.step_at(now)
    for offset in (-1, 0, 1):
        code = codes.hotp(_key(secret), step + offset)
        assert codes.matching_step(secret, code, now) == step + offset
    for offset in (-3, -2, 2, 3):
        code = codes.hotp(_key(secret), step + offset)
        assert codes.matching_step(secret, code, now) in (None, step - 1, step, step + 1)
        # a code two steps away only matches by chance (another step's same digits)
        if codes.matching_step(secret, code, now) is not None:
            assert codes.hotp(_key(secret), codes.matching_step(secret, code, now) or 0) == code


@pytest.mark.parametrize(
    "bad", ["", "12345", "1234567", "abcdef", "12 345", "１２３４５６", "-12345"]
)
def test_malformed_codes_never_match(bad: str) -> None:
    assert codes.matching_step(codes.new_secret(), bad, 1_800_000_000) is None


def test_a_code_with_spaces_around_matches() -> None:
    secret = codes.new_secret()
    code = codes.hotp(_key(secret), codes.step_at(1_800_000_000))
    assert codes.matching_step(secret, f" {code[:3]} {code[3:]} ", 1_800_000_000) is not None


def test_new_secrets_are_160_random_bits_in_base32() -> None:
    made = {codes.new_secret() for _ in range(50)}
    assert len(made) == 50
    for secret in made:
        assert len(secret) == 32 and secret == secret.upper()
        assert len(_key(secret)) == 20


def test_the_otpauth_uri_names_issuer_account_and_parameters() -> None:
    uri = codes.otpauth_uri("JBSWY3DPEHPK3PXP", account="ada@example.com", issuer="Herd & Co")
    parts = urlsplit(uri)
    assert (parts.scheme, parts.netloc) == ("otpauth", "totp")
    assert parts.path == "/Herd%20%26%20Co:ada%40example.com"
    query = parse_qs(parts.query)
    assert query == {
        "secret": ["JBSWY3DPEHPK3PXP"],
        "issuer": ["Herd & Co"],
        "algorithm": ["SHA1"],
        "digits": ["6"],
        "period": ["30"],
    }

"""Signing keys for ID tokens in tests and the OIDC stub: an RSA or EC key with a
`kid`, its public JWK, and tokens signed with it, also wrongly (`alg=none`, HS256
with the public key as the secret), to prove the verifier refuses them."""

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


@dataclass
class SigningKey:
    kid: str
    alg: str = "RS256"
    _private: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._private is None:
            self._private = (
                rsa.generate_private_key(public_exponent=65537, key_size=2048)
                if self.alg == "RS256"
                else ec.generate_private_key(ec.SECP256R1())
            )

    def jwk(self) -> dict[str, Any]:
        algorithm = (
            jwt.algorithms.RSAAlgorithm if self.alg == "RS256" else jwt.algorithms.ECAlgorithm
        )
        public = json.loads(algorithm.to_jwk(self._private.public_key()))
        return {**public, "kid": self.kid, "alg": self.alg, "use": "sig"}

    def public_pem(self) -> bytes:
        return self._private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def sign(self, claims: dict[str, Any], *, kid: str | None = None) -> str:
        headers = {"kid": kid if kid is not None else self.kid}
        return jwt.encode(claims, self._private, algorithm=self.alg, headers=headers)

    def sign_none(self, claims: dict[str, Any]) -> str:
        header = _b64(json.dumps({"alg": "none", "kid": self.kid}).encode())
        return f"{header}.{_b64(json.dumps(claims).encode())}."

    def sign_hs256_with_public_key(self, claims: dict[str, Any]) -> str:
        """The classic confusion: HMAC with the public key as the shared secret."""
        import hashlib  # noqa: PLC0415
        import hmac  # noqa: PLC0415

        header = _b64(json.dumps({"alg": "HS256", "kid": self.kid, "typ": "JWT"}).encode())
        body = _b64(json.dumps(claims).encode())
        signing_input = f"{header}.{body}".encode()
        mac = hmac.new(self.public_pem(), signing_input, hashlib.sha256).digest()
        return f"{header}.{body}.{_b64(mac)}"


def jwks(*keys: SigningKey) -> dict[str, Any]:
    return {"keys": [k.jwk() for k in keys]}


def claims_for(
    *, issuer: str, client_id: str, nonce: str, now: float | None = None, **extra: Any
) -> dict[str, Any]:
    """A valid set of claims; `extra` overrides or adds (None removes)."""
    at = int(now if now is not None else time.time())
    claims: dict[str, Any] = {
        "iss": issuer,
        "aud": client_id,
        "sub": "1234567890",
        "iat": at,
        "exp": at + 3600,
        "nonce": nonce,
        "email": "anna@example.com",
        "email_verified": True,
        "name": "Anna Beispiel",
    }
    for name, value in extra.items():
        if value is None:
            claims.pop(name, None)
        else:
            claims[name] = value
    return claims

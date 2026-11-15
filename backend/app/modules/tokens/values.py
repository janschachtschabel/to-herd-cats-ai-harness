"""A token's clear text and the hash that is all the database keeps (plan M8 decision
2): 32 random bytes (256 bits) behind a recognisable prefix, `herd_pat_` for a
person's token (`herd_agt_` comes with agent tokens, task 4). Lookups go by the hash
alone, so comparing a guess costs the same whatever it matches."""

import hashlib
import secrets

from app.modules.tokens.models import TokenKind

PREFIXES = {TokenKind.PERSONAL: "herd_pat_"}
RANDOM_BYTES = 32


def new_secret(kind: TokenKind) -> str:
    return PREFIXES[kind] + secrets.token_urlsafe(RANDOM_BYTES)


def token_digest(secret: str) -> bytes:
    """SHA-256 of the clear text (any text: a malformed one is simply never found)."""
    return hashlib.sha256(secret.encode("utf-8", "surrogatepass")).digest()

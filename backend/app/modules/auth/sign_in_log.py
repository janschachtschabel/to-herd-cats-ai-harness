"""The security log of signing in and out (ASVS 5.0 V16.3.1): one line per attempt,
`auth.sign_in` with the way (`password`, `oidc`), the outcome as a fixed word (`ok`,
OIDC's `login`/`link`/`signup`/`profile_link`, or the refusal's code), the client's
address, the provider's key and, on success, the person's id; `auth.sign_out` with the
person's id. Refusals are warnings. Never an email, a password, a token, a subject or
any other claim."""

import logging
import uuid

logger = logging.getLogger("app.auth")

SUCCESSES = frozenset({"ok", "login", "link", "signup", "profile_link"})


def log_sign_in(
    method: str,
    outcome: str,
    *,
    client: str | None = None,
    user_id: uuid.UUID | None = None,
    provider: str | None = None,
) -> None:
    fields: dict[str, str] = {"method": method, "outcome": outcome}
    if client:
        fields["client"] = client
    if user_id is not None:
        fields["user_id"] = str(user_id)
    if provider:
        fields["provider"] = provider
    level = logging.INFO if outcome in SUCCESSES else logging.WARNING
    logger.log(level, "auth.sign_in", extra=fields)


def log_sign_out(user_id: uuid.UUID) -> None:
    logger.info("auth.sign_out", extra={"user_id": str(user_id)})

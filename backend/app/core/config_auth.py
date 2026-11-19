"""Sign-in settings (plan M9 decisions 12 to 15): OIDC providers. A part of
`Settings` (`config.py` inherits it); `get_settings()` stays the one source."""

from typing import Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings


class AuthSettings(BaseSettings):
    # Identity providers inside the company network (an in-house Keycloak): host names
    # or private networks (CIDR), comma separated, that discovery, the token endpoint
    # and the JWKS of an OIDC provider may reach (`core/egress_allowance.py`); empty:
    # public addresses only. Set in the environment alone, never through the API.
    oidc_allowed_hosts: str = ""
    # Starts and callbacks of OIDC sign-ins per client address and minute, counted in
    # Postgres across every API node.
    oidc_rate_per_minute: int = Field(default=30, ge=1, le=10_000)
    # A login session ends after this many hours without a request (ASVS 5.0 V7.3.1,
    # J7); 0 switches the idle limit off. Opening the live stream is no use.
    session_idle_hours: int = Field(default=24, ge=0, le=24 * 365)

    @model_validator(mode="after")
    def _oidc_allowed_hosts_parse(self) -> Self:
        from app.core.egress_allowance import parse_allowance  # noqa: PLC0415 (light start)

        parse_allowance(self.oidc_allowed_hosts, "HERD_OIDC_ALLOWED_HOSTS")
        return self

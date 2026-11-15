"""The operator's explicit egress proxy for provider calls (`HERD_AI_EGRESS_PROXY`,
ruling M5 (a)), for both guarded clients (`egress.py`, `egress_x2.py`). Ambient proxy
variables (`HTTPS_PROXY`) are never read: the clients do not trust the environment."""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import unquote, urlsplit


class _Rules(Protocol):
    @property
    def allow_private(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class ProxyTarget:
    """An operator's explicit egress proxy (`HERD_AI_EGRESS_PROXY`, ruling M5 (a)):
    trusted, dialled directly; credentials travel only as proxy authentication."""

    url: str
    auth: tuple[str, str] | None

    @classmethod
    def parse(cls, raw: str) -> "ProxyTarget":
        parts = urlsplit(raw)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("an http(s) proxy URL is needed")
        netloc = f"[{parts.hostname}]" if ":" in parts.hostname else parts.hostname
        if parts.port is not None:
            netloc += f":{parts.port}"
        auth = None
        if parts.username is not None:
            auth = (unquote(parts.username), unquote(parts.password or ""))
        return cls(f"{parts.scheme}://{netloc}", auth)


def proxy_for(rules: _Rules, proxy: str | None) -> ProxyTarget | None:
    """The proxy a call goes through: only for connections that may not reach private
    addresses (a `local` connection is dialled directly, through the guard)."""
    if proxy is None or rules.allow_private:
        return None
    return ProxyTarget.parse(proxy)

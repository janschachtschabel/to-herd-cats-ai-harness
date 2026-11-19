"""One notion of "the same origin" for connectors (review of M10 task 13a, R13a-2).

A secret goes only to the origin it was given for (`connectors/moving.py`), and a
calendar access records the origin it was given for (`purposes.create_personal`).
Both compare the one spelling `origin_of` gives: `https://host[:port]` with

- https only (every connector's server and OAuth endpoint is https, `core/egress.py`);
- the host lower case, a trailing dot dropped, each label 1 to 63 letters, digits,
  hyphens or underscores (an internal service name may carry one), not starting or
  ending with a hyphen, at most 253 characters; a name with other letters
  IDNA-encoded (`bücher.example` is `xn--bcher-kva.example`); no space, percent sign,
  delimiter or any other character;
- a name whose last label is a number is an IPv4 address in dotted decimal, nothing
  else (`127.1`, `0x7f.0.0.1` and `2130706433` are refused: one host, one spelling);
- an IPv6 address in brackets, compressed and lower case, never with a zone;
- https's own port 443 dropped, any other port 1 to 65535 kept as a number;
- no user information.

Anything else raises `InvalidOrigin`: there is no "same" for what has no spelling."""

import ipaddress
import re
from urllib.parse import urlsplit

_LABEL = re.compile(r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?")
_HTTPS_PORT = 443
_MAX_HOST_CHARS = 253


class InvalidOrigin(ValueError):
    """The URL names no https origin `origin_of` can spell."""


def origin_of(url: str) -> str:
    """The canonical origin of an https URL (its path, query and fragment ignored)."""
    if any(c.isspace() or not c.isprintable() for c in url):
        raise InvalidOrigin(url)
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise InvalidOrigin(url) from None
    netloc = parts.netloc
    if parts.scheme != "https" or "@" in netloc or not parts.hostname:
        raise InvalidOrigin(url)
    if netloc.startswith("["):
        host = _ipv6(parts.hostname, url)
    else:
        host = _name(parts.hostname, url)
    if port == 0:
        raise InvalidOrigin(url)
    return f"https://{host}" + ("" if port in (None, _HTTPS_PORT) else f":{port}")


def same_origin(a: str, b: str) -> bool:
    """Whether two URLs name one origin; one that has no spelling is no other's."""
    try:
        return origin_of(a) == origin_of(b)
    except InvalidOrigin:
        return False


def _ipv6(host: str, url: str) -> str:
    if "%" in host:
        raise InvalidOrigin(url)  # a zone names an interface of this machine
    try:
        address = ipaddress.IPv6Address(host)
    except ValueError:
        raise InvalidOrigin(url) from None
    return f"[{address.compressed}]"


def _name(host: str, url: str) -> str:
    bare = host.lower().removesuffix(".")
    try:
        ascii_host = bare.encode("idna").decode("ascii")
    except UnicodeError:
        raise InvalidOrigin(url) from None
    labels = ascii_host.split(".")
    if len(ascii_host) > _MAX_HOST_CHARS or not all(_LABEL.fullmatch(x) for x in labels):
        raise InvalidOrigin(url)
    if labels[-1].isdigit():
        try:
            return str(ipaddress.IPv4Address(ascii_host))
        except ValueError:
            raise InvalidOrigin(url) from None
    return ascii_host

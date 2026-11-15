"""The operator's allowance for private MCP servers (`HERD_MCP_ALLOWED_HOSTS`; M8 Task
7 ruling): a self-hosted server inside the company network (an in-house GitLab) is
reachable only where the operator names it. Set in the environment alone, never
through the API; empty by default.

Entries, comma separated: exact host names (no wildcards, no port; case and a trailing
dot do not matter) or networks in CIDR form (a bare address counts as one host). A
listed name may resolve to private addresses (each answer still judged when
connecting, so a name that turns to a metadata address stays refused); an address in
a listed network may be dialled whatever name led to it. Link-local and metadata
addresses are never allowed (`egress._NEVER`), and a network must lie inside a
private range (`PRIVATE_RANGES`; global addresses need no allowance).
"""

import ipaddress
import re
from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from app.core.egress import EgressRules, IPNetwork

_LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
_HOST = re.compile(rf"{_LABEL}(?:\.{_LABEL})*")
PRIVATE_RANGES: tuple[IPNetwork, ...] = tuple(
    ipaddress.ip_network(n)
    for n in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",  # carrier-grade NAT
        "127.0.0.0/8",
        "fc00::/7",  # unique local
        "::1/128",
    )
)


@dataclass(frozen=True, slots=True)
class PrivateAllowance:
    hosts: frozenset[str] = frozenset()
    networks: tuple[IPNetwork, ...] = ()

    def rules(self, base: EgressRules) -> EgressRules:
        """`base` with this allowance for private targets."""
        return replace(base, private_hosts=self.hosts, private_networks=self.networks)

    def covers(self, url: str) -> bool:
        """Whether the URL's host is listed, by name or as an address in a network (a
        call there is dialled directly, past an operator's egress proxy)."""
        try:
            host = urlsplit(url).hostname
        except ValueError:
            return False
        if not host:
            return False
        if host_key(host) in self.hosts:
            return True
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(address.version == n.version and address in n for n in self.networks)


def host_key(host: str) -> str:
    return host.rstrip(".").lower()


def parse_allowance(raw: str, setting: str = "HERD_MCP_ALLOWED_HOSTS") -> PrivateAllowance:
    """The allowance from the setting's text; ValueError names the setting, never an
    entry. The same form serves `HERD_OIDC_ALLOWED_HOSTS` (an in-house identity
    provider)."""
    hosts: set[str] = set()
    networks: list[IPNetwork] = []
    for entry in (part.strip() for part in raw.split(",")):
        if not entry:
            continue
        network = _network(entry, setting)
        if network is not None:
            networks.append(network)
            continue
        name = host_key(entry)
        if len(name) > 253 or _HOST.fullmatch(name) is None:
            raise ValueError(f"{setting}: an entry is no host name or network")
        hosts.add(name)
    return PrivateAllowance(frozenset(hosts), tuple(networks))


def _network(entry: str, setting: str) -> IPNetwork | None:
    try:
        network = ipaddress.ip_network(entry, strict=False)
    except ValueError:
        if "/" in entry:
            raise ValueError(f"{setting}: a network is not valid") from None
        return None
    if not any(network.version == r.version and network.subnet_of(r) for r in PRIVATE_RANGES):  # type: ignore[arg-type]
        raise ValueError(f"{setting}: a network lies outside the private ranges")
    return network

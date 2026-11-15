"""The operator's allowance for private MCP servers (`HERD_MCP_ALLOWED_HOSTS`, M8 Task
7 ruling): exact host names or networks, empty by default, set only in the
environment. A listed name may resolve to private addresses, a listed network may be
dialled; everything else stays as the guard rules, and link-local or metadata
addresses are never allowed."""

import ipaddress

import pytest
from pydantic import ValidationError

from app.core import egress
from app.core.config import Settings
from app.core.egress import EgressBlocked, EgressRules, Network
from app.core.egress_allowance import PrivateAllowance, parse_allowance

PUBLIC_ONLY = EgressRules(allow_private=False, allow_http=False)


def _rules(raw: str) -> EgressRules:
    return parse_allowance(raw).rules(PUBLIC_ONLY)


def test_empty_allows_nothing_more() -> None:
    assert parse_allowance("") == PrivateAllowance()
    assert parse_allowance(" , ") == PrivateAllowance()
    assert _rules("") == PUBLIC_ONLY


def test_names_and_networks_are_parsed() -> None:
    allowance = parse_allowance("GitLab.Corp.example., 10.20.0.0/16, 192.168.1.7, fd00:1::/64")
    assert allowance.hosts == frozenset({"gitlab.corp.example"})
    assert allowance.networks == (
        ipaddress.ip_network("10.20.0.0/16"),
        ipaddress.ip_network("192.168.1.7/32"),
        ipaddress.ip_network("fd00:1::/64"),
    )


@pytest.mark.parametrize(
    "raw",
    [
        "*.corp.example",  # no wildcards
        "https://gitlab.corp.example",  # a name, not a URL
        "gitlab.corp.example:443",
        "bad_name.example",
        "10.0.0.0/33",
        "0.0.0.0/0",  # holds global addresses: those need no allowance
        "8.8.8.0/24",
        "169.254.0.0/16",  # link-local and metadata: never
        "a" * 254,
    ],
)
def test_odd_entries_are_refused_without_echoing_them(raw: str) -> None:
    with pytest.raises(ValueError) as caught:
        parse_allowance(raw)
    assert raw not in str(caught.value)


def test_the_setting_is_checked_at_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_MCP_ALLOWED_HOSTS", "*.corp.example")
    with pytest.raises(ValidationError):
        Settings()
    monkeypatch.setenv("HERD_MCP_ALLOWED_HOSTS", "gitlab.corp.example, 10.0.0.0/8")
    assert Settings().mcp_allowed_hosts == "gitlab.corp.example, 10.0.0.0/8"
    monkeypatch.delenv("HERD_MCP_ALLOWED_HOSTS")
    assert Settings().mcp_allowed_hosts == ""


def test_a_listed_network_may_be_dialled_but_never_metadata() -> None:
    rules = _rules("10.20.0.0/16")
    egress.check_address(ipaddress.ip_address("10.20.3.4"), rules)
    egress.check_address(ipaddress.ip_address("::ffff:10.20.3.4"), rules)
    for refused in ("10.21.0.1", "192.168.1.1", "127.0.0.1", "169.254.169.254"):
        with pytest.raises(EgressBlocked):
            egress.check_address(ipaddress.ip_address(refused), rules)


def test_base_urls_follow_the_allowance() -> None:
    rules = _rules("gitlab.corp.example, localhost, 10.20.0.0/16")
    assert egress.check_base_url("https://10.20.0.5/mcp", rules) == "https://10.20.0.5/mcp"
    assert egress.check_base_url("https://localhost/mcp", rules) == "https://localhost/mcp"
    for refused in ("https://10.21.0.5/mcp", "https://169.254.169.254/", "http://10.20.0.5/"):
        with pytest.raises(EgressBlocked):
            egress.check_base_url(refused, rules)
    with pytest.raises(EgressBlocked):
        egress.check_base_url("https://localhost/mcp", PUBLIC_ONLY)


def _answering(*answers: str) -> Network:
    async def resolve(host: str, port: int) -> list[str]:
        return list(answers)

    return Network(resolver=resolve)


async def _resolved(rules: EgressRules, network: Network, host: str) -> list[str]:
    found = await egress.checked_addresses(
        rules, network, host, 443, 1.0, TimeoutError, ConnectionError
    )
    return [str(a) for a in found]


async def test_a_listed_name_may_resolve_privately_a_name_not_listed_may_not() -> None:
    rules = _rules("gitlab.corp.example")
    private = _answering("10.1.2.3")
    assert await _resolved(rules, private, "gitlab.corp.example") == ["10.1.2.3"]
    assert await _resolved(rules, private, "GITLAB.corp.example.") == ["10.1.2.3"]
    for name in ("evil.example", "x.gitlab.corp.example", "gitlab.corp.example.evil"):
        with pytest.raises(EgressBlocked):
            await _resolved(rules, private, name)


async def test_a_listed_name_never_reaches_metadata() -> None:
    """DNS rebinding against a listed name: each answer is still judged, so a name that
    turns to a metadata address stays refused."""
    rules = _rules("gitlab.corp.example")
    for answer in ("169.254.169.254", "fd00:ec2::254", "::ffff:169.254.169.254"):
        with pytest.raises(EgressBlocked):
            await _resolved(rules, _answering("10.1.2.3", answer), "gitlab.corp.example")


def test_the_allowance_names_the_hosts_it_covers() -> None:
    allowance = parse_allowance("gitlab.corp.example, 10.20.0.0/16")
    assert allowance.covers("https://gitlab.corp.example/api/v4/mcp")
    assert allowance.covers("https://GitLab.corp.example.:8443/mcp")
    assert allowance.covers("https://10.20.1.1/mcp")
    assert not allowance.covers("https://gitlab.com/api/v4/mcp")
    assert not allowance.covers("https://10.21.1.1/mcp")
    assert not allowance.covers("not a url")

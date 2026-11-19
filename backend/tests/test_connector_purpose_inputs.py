"""What `purposes.create_personal` takes (fix wave of the review of M10 task 13a,
`review-task-13a.md`): a secret that is empty or blank is refused as invalid, never by
the database (R13a-1); an origin has one spelling, the one `connectors/moving.py`
compares (R13a-2); the function serves calendar accesses only (R13a-12)."""

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.modules.connectors import purposes
from app.modules.connectors.models import AuthKind, Connector
from app.modules.connectors.moving import moved_origin
from app.modules.connectors.origins import InvalidOrigin, origin_of
from app.modules.connectors.purposes import Purpose
from tests.factories_calendar import actor_of
from tests.factories_connectors import PERSONAL
from tests.factories_dms import People
from tests.factories_purposes import ORIGIN, sync_on


async def _count(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).select_from(Connector)) or 0)


@pytest.mark.parametrize("blank", ["", " ", "   ", "\t", "\n"])
async def test_a_blank_secret_is_refused_as_invalid(
    blank: str, people: People, session: AsyncSession, secret_key: None
) -> None:
    await sync_on(people.admin)
    actor = await actor_of(session, people.users["alice"])
    before = await _count(session)
    for kind, header in ((AuthKind.HEADER, "Authorization"), (AuthKind.BEARER, None)):
        with pytest.raises(ValidationFailed) as refused:
            async with session.begin_nested():
                await purposes.create_personal(
                    session,
                    actor,
                    purpose=Purpose.CALENDAR,
                    kind=kind,
                    origin=ORIGIN,
                    header_name=header,
                    secret=SecretStr(blank),
                )
        assert refused.value.code == "connector.secret_invalid"
    assert await _count(session) == before


@pytest.mark.parametrize("blank", ["", "   "])
async def test_a_blank_secret_at_the_connector_routes_is_a_422(
    blank: str, ai_people: People
) -> None:
    """The M8 routes, the only ones that take a connector's secret today."""
    body = {"name": "Blank", "auth_kind": "bearer", "secret": {"value": blank}}
    r = await ai_people.alice.post(PERSONAL, json=body)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "secrets.value_invalid"


@pytest.mark.parametrize(
    ("given", "made"),
    [
        ("https://caldav.example.com", "https://caldav.example.com"),
        ("https://CalDAV.Example.COM", "https://caldav.example.com"),
        ("https://caldav.example.com:443", "https://caldav.example.com"),
        ("https://caldav.example.com.", "https://caldav.example.com"),
        ("https://caldav.example.com:8443", "https://caldav.example.com:8443"),
        ("https://caldav.example.com:08443", "https://caldav.example.com:8443"),
        ("https://bücher.example", "https://xn--bcher-kva.example"),
        ("https://xn--bcher-kva.example", "https://xn--bcher-kva.example"),
        ("https://radicale_test:5232", "https://radicale_test:5232"),
        ("https://192.0.2.10", "https://192.0.2.10"),
        ("https://[::1]", "https://[::1]"),
        ("https://[2001:DB8:0:0::1]:8443", "https://[2001:db8::1]:8443"),
        ("https://[2001:db8::1]:443", "https://[2001:db8::1]"),
    ],
)
def test_an_origin_has_one_spelling(given: str, made: str) -> None:
    assert purposes.bare_origin(given) == made
    assert origin_of(given + "/some/path?q=1") == made  # what `moving` compares


@pytest.mark.parametrize(
    "given",
    [
        "http://caldav.example.com",
        "ftp://caldav.example.com",
        "caldav.example.com",
        "https://",
        "https://:8443",
        "https://caldav.example.com:0",
        "https://caldav.example.com:65536",
        "https://caldav.example.com:x",
        "https://user@caldav.example.com",
        "https://user:pw@caldav.example.com",
        "https://caldav.example.com/",
        "https://caldav.example.com/dav",
        "https://caldav.example.com?x=1",
        "https://caldav.example.com#f",
        "https://-caldav.example.com",
        "https://caldav-.example.com",
        "https://cal..example.com",
        "https://" + "a" * 64 + ".example",
        "https://" + ".".join(["abcdefgh"] * 29),
        "https://127.1",
        "https://0x7f.0.0.1",
        "https://2130706433",
        "https://[fe80::1%25eth0]",
        "https://[1.2.3.4]",
        "https://[::1",
        " https://caldav.example.com",
        "https://caldav.example.com ",
        "https://caldav.example.com\n",
    ],
)
def test_anything_but_an_https_origin_is_refused(given: str) -> None:
    with pytest.raises(ValidationFailed) as refused:
        purposes.bare_origin(given)
    assert refused.value.code == "connector.origin_invalid"


@pytest.mark.parametrize(
    ("before", "after", "moved"),
    [
        ("https://a.test/mcp", "https://A.test:443/other/", False),
        ("https://a.test/mcp", "https://a.test./mcp", False),
        ("https://[2001:db8::1]/mcp", "https://[2001:DB8:0::1]:443/x", False),
        ("https://bücher.example/mcp", "https://xn--bcher-kva.example/mcp", False),
        ("https://a.test/mcp", "https://a.test:8443/mcp", True),
        ("https://a.test/mcp", "https://b.test/mcp", True),
        ("https://[::1]/mcp", "https://[::2]/mcp", True),
        # What the normaliser refuses cannot be shown to be the same origin.
        ("https://a.test/mcp", "https://a%20test/mcp", True),
        ("https://a%20test/mcp", "https://a.test/mcp", True),
    ],
)
def test_moving_compares_the_same_origins(before: str, after: str, moved: bool) -> None:
    """`moving.moved_origin` and `bare_origin` share one notion of "the same origin"."""
    assert moved_origin(before, after) is moved
    if not moved:
        assert origin_of(before) == origin_of(after)
    assert not moved_origin(before, before)  # an unchanged URL never moves


def test_origin_of_refuses_with_its_own_error() -> None:
    with pytest.raises(InvalidOrigin):
        origin_of("https://a b/mcp")


async def test_create_personal_and_personal_repository_serve_no_mcp_connector(
    ai_people: People, session: AsyncSession
) -> None:
    """R13a-12: an MCP connector is made by `ConnectorService` (names, `ai.use`'s 404);
    asking these for one is a programming error, not a request to answer."""
    actor = await actor_of(session, ai_people.users["alice"])
    with pytest.raises(ValueError, match="mcp"):
        await purposes.personal_repository(session, actor, Purpose.MCP)
    with pytest.raises(ValueError, match="mcp"):
        await purposes.create_personal(
            session,
            actor,
            purpose=Purpose.MCP,
            kind=AuthKind.BEARER,
            origin=ORIGIN,
            secret=SecretStr("abc"),
        )

"""Review of M10 task 13a (`.superpowers/sdd/m10/review-task-13a.md`): what
`purposes.create_personal` does with what it is given. Each test fails on fd4644d."""

from urllib.parse import urlsplit

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationFailed
from app.modules.connectors import purposes
from app.modules.connectors.models import AuthKind
from app.modules.connectors.purposes import Purpose
from tests.factories_calendar import actor_of
from tests.factories_dms import People
from tests.factories_purposes import ORIGIN, sync_on


async def test_an_empty_secret_is_refused_as_invalid_never_by_the_database(
    people: People, session: AsyncSession, secret_key: None
) -> None:
    """R13a-1: `SecretStr("")` is not None but falsy, so it passes the kind check and
    is then stored as no secret at all: the database's check answers (500)."""
    await sync_on(people.admin)
    actor = await actor_of(session, people.users["alice"])
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
                    secret=SecretStr(""),
                )
        assert refused.value.code in {"connector.secret_invalid", "secrets.value_invalid"}


@pytest.mark.parametrize(
    ("given", "host", "port"),
    [("https://[::1]", "::1", None), ("https://[2001:db8::1]:8443", "2001:db8::1", 8443)],
)
def test_an_ipv6_origin_stays_an_origin(given: str, host: str, port: int | None) -> None:
    """R13a-2: the brackets are dropped (`https://::1`, `https://2001:db8::1:8443`):
    what is recorded as the origin is no URL and names no host."""
    try:
        made = purposes.bare_origin(given)
    except ValidationFailed as refused:  # refusing address literals is an answer, too
        assert refused.code == "connector.origin_invalid"
        return
    parts = urlsplit(made)
    assert (parts.scheme, parts.hostname, parts.port) == ("https", host, port)


@pytest.mark.parametrize(
    "given",
    ["https://a b", "https://a<script>", "https://h\\x", "https://a,b", "https://a%20b"],
)
def test_an_origin_names_a_host(given: str) -> None:
    """R13a-2: anything `urlsplit` calls a hostname passes and goes into the audit
    entry as the origin the access was given for."""
    with pytest.raises(ValidationFailed) as refused:
        purposes.bare_origin(given)
    assert refused.value.code == "connector.origin_invalid"


def test_one_origin_has_one_spelling() -> None:
    """R13a-2: `connectors/moving.origin` knows `:443` as https's own port; the origin
    recorded here keeps it, so one origin has two spellings to compare later."""
    assert purposes.bare_origin("https://Host:443") == purposes.bare_origin("https://host")

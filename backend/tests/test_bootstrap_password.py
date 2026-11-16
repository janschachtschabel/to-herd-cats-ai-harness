"""The first owner's password passes the same checks as every other password (module
review M9a, N6; ASVS 5.0 V6.2.4, V6.2.11, V6.2.12): a breached one or one holding a
context word (the organisation, the address) is refused, nothing is created, and the
start fails with a clear error. Once someone exists, the variables are not read."""

import logging

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import launch
from app.core.config import Settings
from app.modules.orgs.models import Organization
from app.modules.orgs.service import BootstrapRefused, ensure_bootstrap
from app.modules.users.models import User


def _boot(password: str) -> Settings:
    return Settings(
        bootstrap_admin_email="owner@firma.example",
        bootstrap_admin_password=SecretStr(password),
        bootstrap_org_name="Firma Nord",
    )


@pytest.mark.parametrize(
    ("password", "code"),
    [
        ("password1234", "auth.password_common"),  # on the breached list
        ("firmanord-2026!", "auth.password_context"),  # the organisation's name
        ("owner-lantern-73", "auth.password_context"),  # the address's local part
    ],
)
async def test_a_guessable_bootstrap_password_creates_nobody(
    session: AsyncSession, password: str, code: str
) -> None:
    with pytest.raises(BootstrapRefused) as refused:
        await ensure_bootstrap(session, _boot(password))
    assert refused.value.code == code
    assert await session.scalar(select(func.count()).select_from(User)) == 0
    assert await session.scalar(select(func.count()).select_from(Organization)) == 0


async def test_a_refused_bootstrap_stops_the_start_with_a_clear_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def refuse(session: object, settings: Settings) -> None:
        raise BootstrapRefused("auth.password_common")

    class FakeSession:
        async def __aenter__(self) -> "FakeSession":
            return self

        async def __aexit__(self, *exc: object) -> None:
            pass

    class FakeDatabase:
        session_factory = FakeSession

    monkeypatch.setattr(launch, "get_database", lambda: FakeDatabase())
    monkeypatch.setattr(launch, "ensure_bootstrap", refuse)
    caplog.set_level(logging.ERROR)
    with pytest.raises(SystemExit) as stopped:
        await launch.bootstrap(_boot("password1234"))
    assert stopped.value.code == launch.BOOTSTRAP_EXIT_CODE
    (record,) = [r for r in caplog.records if r.getMessage().startswith("bootstrap refused")]
    assert "HERD_BOOTSTRAP_ADMIN_PASSWORD" in record.getMessage()
    assert "password1234" not in caplog.text


async def test_once_someone_exists_the_bootstrap_password_is_not_checked(
    session: AsyncSession, owner_user: User
) -> None:
    await ensure_bootstrap(session, _boot("password1234"))
    assert await session.scalar(select(func.count()).select_from(User)) == 1


async def test_a_good_bootstrap_password_creates_the_owner(session: AsyncSession) -> None:
    await ensure_bootstrap(session, _boot("lantern-orbit-73-q"))
    owner = await session.scalar(select(User))
    assert owner is not None and owner.system_role == "owner"

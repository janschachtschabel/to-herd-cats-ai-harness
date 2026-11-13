"""The database password: separate from HERD_DATABASE_URL, merged in by Settings."""

import logging

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.migrations import upgrade_head

URL = "postgresql+asyncpg://herd@db:5432/herd"
SPECIAL = "p@ss:w/rd%20#?&=+ é\\"


@pytest.fixture(autouse=True)
def _no_password_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("HERD_DATABASE_URL", "HERD_DATABASE_PASSWORD", "HERD_DATABASE_PASSWORD_FILE"):
        monkeypatch.delenv(name, raising=False)


def test_url_with_password_keeps_working() -> None:
    url = Settings(database_url="postgresql+asyncpg://herd:herd@localhost:5433/herd").database()
    assert url.password == "herd"
    assert (url.username, url.host, url.port, url.database) == ("herd", "localhost", 5433, "herd")


def test_password_from_env_is_merged_into_the_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_DATABASE_URL", URL)
    monkeypatch.setenv("HERD_DATABASE_PASSWORD", "s3cret")
    url = Settings().database()
    assert url.password == "s3cret"
    assert (url.username, url.host, url.database) == ("herd", "db", "herd")


def test_password_from_file(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    secret = tmp_path / "password"
    secret.write_text("from-file\n")  # a mounted secret often ends with a newline
    monkeypatch.setenv("HERD_DATABASE_URL", URL)
    monkeypatch.setenv("HERD_DATABASE_PASSWORD_FILE", str(secret))
    assert Settings().database().password == "from-file"


def test_separate_password_wins_over_one_in_the_url() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://herd:old@db/herd", database_password="new"
    )
    assert settings.database().password == "new"


def test_password_and_password_file_together_are_refused(tmp_path) -> None:
    secret = tmp_path / "password"
    secret.write_text("a")
    with pytest.raises(ValidationError, match="not both"):
        Settings(database_password="b", database_password_file=secret)


def test_missing_or_empty_password_file_is_refused(tmp_path) -> None:
    with pytest.raises(ValidationError, match="cannot be read"):
        Settings(database_password_file=tmp_path / "missing")
    empty = tmp_path / "empty"
    empty.write_text("\n")
    with pytest.raises(ValidationError, match="is empty"):
        Settings(database_password_file=empty)


def test_special_characters_are_escaped_and_survive_the_round_trip() -> None:
    url = Settings(database_url=URL, database_password=SPECIAL).database()
    rendered = url.render_as_string(hide_password=False)
    assert SPECIAL not in rendered  # escaped, not pasted in
    reparsed = make_url(rendered)
    assert reparsed.password == SPECIAL
    assert (reparsed.host, reparsed.port, reparsed.database) == ("db", 5432, "herd")


def test_password_is_not_in_repr_str_or_logs(caplog: pytest.LogCaptureFixture) -> None:
    settings = Settings(database_url=URL, database_password="hunter2-secret")
    url = settings.database()
    caplog.set_level(logging.DEBUG)
    logging.getLogger("test").info("settings %s url %s %r", settings, url, url)
    for shown in (repr(settings), str(settings), str(url), repr(url), caplog.text):
        assert "hunter2-secret" not in shown


async def test_engine_connects_with_the_separate_password() -> None:
    """End to end: a URL without password plus HERD_DATABASE_PASSWORD reaches Postgres."""
    test_url = make_url(get_settings().test_database_url)
    assert test_url.password, "the test database URL carries the password"
    bare = test_url.set(password=None).render_as_string(hide_password=False)
    settings = Settings(database_url=bare, database_password=test_url.password)
    engine = create_async_engine(settings.database())
    try:
        async with engine.connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar() == 1
    finally:
        await engine.dispose()


def test_a_settings_error_does_not_echo_the_input(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_DATABASE_PASSWORD", "pw")  # short: shown whole if echoed
    monkeypatch.setenv("HERD_DATABASE_PASSWORD_FILE", "/nonexistent")
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert "'pw'" not in str(caught.value)
    assert "input_value" not in str(caught.value)


@pytest.fixture
def separate_password_env(monkeypatch: pytest.MonkeyPatch):
    """HERD_DATABASE_URL points at the test database with a wrong password in the URL;
    only the separate HERD_DATABASE_PASSWORD is right."""
    test_url = make_url(get_settings().test_database_url)
    wrong = test_url.set(password="wrong").render_as_string(hide_password=False)
    monkeypatch.setenv("HERD_DATABASE_URL", wrong)
    monkeypatch.setenv("HERD_DATABASE_PASSWORD", test_url.password or "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_the_app_engine_uses_the_resolved_url(separate_password_env) -> None:
    database = Database()
    try:
        async with database.engine.connect() as connection:
            assert (await connection.execute(text("SELECT 1"))).scalar() == 1
    finally:
        await database.dispose()


def test_alembic_uses_the_resolved_url(separate_password_env, engine) -> None:
    """`engine` has migrated the test database; upgrading again connects and is a no-op."""
    upgrade_head()


def test_no_setting_without_a_reader() -> None:
    """HERD_INTERNAL_TOKEN comes with its first reader (M2, /internal/*), not before."""
    assert "internal_token" not in Settings.model_fields


def test_bootstrap_password_is_hidden(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("HERD_BOOTSTRAP_ADMIN_PASSWORD", "boot-pw-7e21")
    settings = Settings()
    caplog.set_level(logging.DEBUG)
    logging.getLogger("test").info("settings %s %r", settings, settings)
    shown = [
        repr(settings),
        str(settings),
        str(settings.model_dump()),
        settings.model_dump_json(),
        caplog.text,
    ]
    for text_ in shown:
        assert "boot-pw-7e21" not in text_
    # The reader still gets the value.
    assert settings.bootstrap_admin_password.get_secret_value() == "boot-pw-7e21"


@pytest.mark.parametrize("password", ["short-pw1", "x" * 201])
def test_bootstrap_password_follows_the_password_rule(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    """The first owner's password meets the same rule as any other (10–200 characters);
    the start fails with a message that does not echo the value."""
    monkeypatch.setenv("HERD_BOOTSTRAP_ADMIN_PASSWORD", password)
    with pytest.raises(ValidationError) as caught:
        Settings()
    message = str(caught.value)
    assert "HERD_BOOTSTRAP_ADMIN_PASSWORD" in message and "10" in message
    assert password not in message


def test_no_bootstrap_password_is_allowed() -> None:
    """Without one, bootstrap is skipped (and says so in the log)."""
    assert Settings(bootstrap_admin_password="").bootstrap_admin_password.get_secret_value() == ""

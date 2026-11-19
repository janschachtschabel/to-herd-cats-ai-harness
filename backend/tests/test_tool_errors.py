"""A failing PostgreSQL tool says why in the log, never data or a password (R18-2)."""

import logging
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings
from app.ops import pgtools
from app.ops.tool_errors import QUERY_FAILED, reason


def test_a_connection_error_is_the_reason() -> None:
    said = (
        b'pg_dump: error: connection to server at "db" (10.0.0.5), port 5432 failed: '
        b'root certificate file "/home/app/.postgresql/root.crt" does not exist\n'
        b"DETAIL: something\n"
    )
    assert reason(said) == (
        'connection to server at "db" (10.0.0.5), port 5432 failed: '
        'root certificate file "/home/app/.postgresql/root.crt" does not exist'
    )


def test_an_sql_error_is_only_named_since_it_may_quote_data() -> None:
    said = (
        b"pg_restore: error: could not execute query: ERROR:  duplicate key value\n"
        b"DETAIL:  Key (email)=(ada@example.com) already exists.\n"
    )
    assert reason(said) == QUERY_FAILED
    assert reason(b'psql:<stdin>:12: ERROR:  invalid input syntax: "x"\n') is None


def test_passwords_and_user_information_are_masked() -> None:
    said = b"psql: error: postgresql://app:s3cret@db/herd password=hunter2 failed\n"
    found = reason(said)
    assert found is not None
    assert "s3cret" not in found and "hunter2" not in found


async def test_a_failed_dump_logs_why(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    url = make_url(get_settings().test_database_url).set(port=1, password="pw-not-logged")
    settings = Settings(database_url=url.render_as_string(hide_password=False))
    with caplog.at_level(logging.WARNING), pytest.raises(pgtools.ToolFailed):
        await pgtools.dump(settings, "00000003-0000001B-1", tmp_path / "out.dump")
    records = [r for r in caplog.records if r.getMessage() == "backup.tool_failed"]
    assert len(records) == 1
    record = records[0]
    assert record.__dict__["tool"] == "pg_dump"
    assert record.__dict__["code"] == "backup.dump_failed"
    assert "connection to server" in record.__dict__["reason"]
    assert "pw-not-logged" not in caplog.text

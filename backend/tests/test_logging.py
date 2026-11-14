import json
import logging

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import Settings, get_settings
from app.core.db import Database
from app.core.logging import configure_logging, log_context
from app.core.telemetry import current_trace_ids, span_exporter_from_env
from app.web.public import create_public_app
from tests.conftest import json_lines, last_line
from tests.factories import CSRF


async def test_request_line_is_json_with_required_fields(client, capsys):
    await client.get("/api/_test/ok")
    line = json.loads(last_line(capsys, "http.request"))
    assert line["service"] == "to-herd-cats-ai"
    assert {"timestamp", "level", "trace_id", "span_id", "message"} <= line.keys()
    assert line["path"] == "/api/_test/ok" and line["status"] == 200 and "duration_ms" in line


async def test_incoming_traceparent_is_continued(client, capsys):
    tp = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
    r = await client.get("/api/_test/not-found", headers={"traceparent": tp})
    assert r.json()["error"]["trace_id"] == "0af7651916cd43dd8448eb211c80319c"


async def test_client_trace_id_is_logged(client, capsys):
    await client.get("/api/_test/ok", headers={"x-client-trace-id": "abc-123"})
    assert json.loads(last_line(capsys, "http.request"))["client_trace_id"] == "abc-123"


async def test_secrets_never_reach_logs(client, capsys):
    await client.post(
        "/api/_test/boom-post",
        json={"password": "hunter2-secret"},
        headers={"Cookie": "herd_session=sess-secret", "Authorization": "Bearer tok-secret"},
    )
    out = capsys.readouterr().out + capsys.readouterr().err
    for secret in ("hunter2-secret", "sess-secret", "tok-secret"):
        assert secret not in out


async def test_unhandled_error_is_logged_and_agrees_with_error_body(client, capsys):
    r = await client.post("/api/_test/boom-post", json={"password": "x"})
    trace_id = r.json()["error"]["trace_id"]
    lines = {line["message"]: line for line in json_lines(capsys.readouterr().out)}
    error, request = lines["unhandled exception"], lines["http.request"]
    assert error["level"] == "ERROR" and "RuntimeError" in error["exc_info"]
    assert error["trace_id"] == trace_id
    assert request["status"] == 500 and request["trace_id"] == trace_id


async def test_request_line_uses_the_route_template(client, capsys):
    await client.get("/api/_test/items/42")
    line = json.loads(last_line(capsys, "http.request"))
    assert line["path"] == "/api/_test/items/{item_id}" and line["method"] == "GET"


async def test_unmatched_path_is_logged_raw(client, capsys):
    await client.get("/api/_test/nowhere")
    assert json.loads(last_line(capsys, "http.request"))["path"] == "/api/_test/nowhere"


async def test_malformed_client_trace_id_is_dropped(client, capsys):
    await client.get("/api/_test/ok", headers={"x-client-trace-id": "evil\nvalue" + "x" * 200})
    assert "client_trace_id" not in json.loads(last_line(capsys, "http.request"))


async def test_b3_propagator_is_selected_by_env(monkeypatch, capsys):
    monkeypatch.setenv("OTEL_PROPAGATORS", "b3")
    app = create_public_app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get(
            "/api/_test/not-found",
            headers={"b3": "80f198ee56343ba864fe8b2a57d3eff7-e457b5a2e4d86bd1-1"},
        )
    assert r.json()["error"]["trace_id"] == "80f198ee56343ba864fe8b2a57d3eff7"


def test_log_context_fields_appear_in_lines(capsys):
    with log_context(org_id="org-1", actor="user:u-1"):
        logging.getLogger("app.test").info("inside")
    logging.getLogger("app.test").info("outside")
    lines = {line["message"]: line for line in json_lines(capsys.readouterr().out)}
    inside, outside = lines["inside"], lines["outside"]
    assert inside["org_id"] == "org-1" and inside["actor"] == "user:u-1"
    assert "org_id" not in outside


def test_current_trace_ids_without_span_are_fresh_hex():
    trace_id, span_id = current_trace_ids()
    assert len(trace_id) == 32 and len(span_id) == 16
    int(trace_id, 16), int(span_id, 16)
    assert current_trace_ids()[0] != trace_id


def test_text_format_is_human_readable(capsys):
    configure_logging(Settings(log_format="text"))
    try:
        logging.getLogger("app.test").warning("plain words")
        out = capsys.readouterr().out
        assert "plain words" in out and "WARNING" in out
        with pytest.raises(json.JSONDecodeError):
            json.loads(out.strip().splitlines()[-1])
    finally:
        configure_logging(Settings(log_format="json"))


def test_log_level_is_applied():
    configure_logging(Settings(log_level="WARNING"))
    try:
        assert logging.getLogger().level == logging.WARNING
    finally:
        configure_logging(Settings())


@pytest.mark.parametrize("name", ["httpx2", "httpcore2", "openai", "httpcore", "httpx"])
def test_http_clients_stay_quiet_at_debug(name):
    """Their DEBUG lines quote response headers (review M5, finding 4)."""
    configure_logging(Settings(log_level="DEBUG"))
    try:
        assert not logging.getLogger(f"{name}.http11").isEnabledFor(logging.DEBUG)
        assert logging.getLogger(name).isEnabledFor(logging.WARNING)
    finally:
        configure_logging(Settings())


def test_uvicorn_color_message_is_not_a_field(capsys):
    logging.getLogger("uvicorn.error").info("plain", extra={"color_message": "\x1b[1mplain"})
    assert "color_message" not in json.loads(last_line(capsys, "plain"))


def test_otlp_exporter_only_when_endpoint_is_set():
    assert span_exporter_from_env({}) is None
    assert span_exporter_from_env({"OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector:4318"})


async def test_plain_starlette_routes_are_logged_by_template(client, capsys):
    await client.get("/api/openapi.json")
    assert json.loads(last_line(capsys, "http.request"))["path"] == "/api/openapi.json"


async def test_database_errors_log_neither_parameters_nor_values(client, capsys):
    """A failing statement's bound parameters and the database's message (which quotes
    the value) stay out of the log; the statement's class and SQLSTATE are there."""
    marker = "SECRET-MARKER-4711"
    r = await client.post("/api/_test/db-error", json={"v": marker}, headers=CSRF)
    assert r.status_code == 500 and marker not in r.text
    captured = capsys.readouterr()
    assert marker not in captured.out + captured.err
    errors = [line for line in json_lines(captured.out) if line["message"] == "unhandled exception"]
    assert len(errors) == 1
    assert "sqlstate=22P02" in errors[0]["exc_info"] and "CAST($1 AS text)" in errors[0]["exc_info"]


async def test_unhandled_error_is_answered_and_logged_once(capsys):
    """The app answers the 500 itself and does not re-raise: the server (uvicorn) would
    log the same exception a second time, with its message."""
    app = create_public_app()
    transport = ASGITransport(app=app, raise_app_exceptions=True)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/api/_test/boom")
    assert r.status_code == 500 and r.json()["error"]["code"] == "internal"
    lines = json_lines(capsys.readouterr().out)
    assert [line["message"] for line in lines].count("unhandled exception") == 1


async def test_engine_errors_carry_no_bound_parameters():
    """Pinned without the log formatter: the raw exception text of a failing statement
    names neither the bound value nor a parameter list (`hide_parameters=True`)."""
    marker = "SECRET-MARKER-0815"
    database = Database(get_settings().test_database_url)
    try:
        async with database.engine.connect() as conn:
            with pytest.raises(DBAPIError) as caught:
                await conn.execute(text("SELECT CAST(:v AS text), 1 / 0"), {"v": marker})
    finally:
        await database.dispose()
    assert "division by zero" in str(caught.value)
    assert marker not in str(caught.value) and "[parameters:" not in str(caught.value)

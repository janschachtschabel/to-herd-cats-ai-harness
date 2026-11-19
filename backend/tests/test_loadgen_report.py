"""The load test's evaluation (plan M9 Task 10, decision 20): percentiles, the targets
per kind of request, live delivery and error counts, from a fixed series. The code is
deploy/compose/loadreport.py; it needs neither a database nor a server."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "compose" / "loadreport.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("loadreport", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["loadreport"] = module  # dataclasses look their module up
    writes, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # no __pycache__ in deploy/
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = writes
    return module


report = _module()


def _series(name: str, millis: range | list[int], status: str = "200") -> list[object]:
    return [report.Sample(name, ms / 1000, status) for ms in millis]


def test_percentile_is_the_nearest_rank() -> None:
    values = [float(v) for v in range(100, 0, -1)]  # 100 … 1, unsorted on purpose
    assert report.percentile(values, 0.50) == 50
    assert report.percentile(values, 0.95) == 95
    assert report.percentile(values, 0.99) == 99
    assert report.percentile(values, 1.0) == 100
    assert report.percentile([7.0], 0.95) == 7
    assert report.percentile([1.0, 2.0, 3.0], 0.5) == 2


def test_percentile_of_nothing_is_refused() -> None:
    with pytest.raises(ValueError):
        report.percentile([], 0.95)


def test_summary_per_endpoint_counts_statuses() -> None:
    samples = [
        *_series("page_read", range(1, 101)),
        *_series("page_read", [900], "503"),
        *_series("page_read", [30_000], "ReadTimeout"),
        *_series("ticket_move", [40, 50], "409"),
    ]
    summaries = report.summarize(samples)
    read = summaries["page_read"]
    assert read.n == 102
    assert read.p95_ms == pytest.approx(97)
    assert read.max_ms == pytest.approx(30_000)
    assert (read.server_errors, read.transport_errors, read.client_errors) == (1, 1, 0)
    move = summaries["ticket_move"]
    assert (move.server_errors, move.transport_errors, move.client_errors) == (0, 0, 2)


def test_reads_and_writes_meet_their_own_targets() -> None:
    samples = [
        *_series("page_read", [100] * 94 + [301] * 6),  # P95 301 ms: misses 300
        *_series("search", [250] * 100),
        *_series("message_write", [480] * 100),  # a write may take 500 ms
    ]
    verdicts = {v.name: v for v in report.verdicts(samples, live_delays=[], live_missing=0)}
    assert verdicts["page_read"].target_ms == 300 and not verdicts["page_read"].met
    assert verdicts["page_read"].value_ms == pytest.approx(301)
    assert verdicts["search"].met
    assert verdicts["message_write"].target_ms == 500 and verdicts["message_write"].met


def test_every_scenario_endpoint_has_a_kind() -> None:
    assert {
        "page_read": "read",
        "search": "read",
        "board": "read",
        "my_tickets": "read",
        "message_write": "write",
        "ticket_move": "write",
        "page_save": "write",
    } == report.KINDS
    assert report.TARGETS_MS == {"read": 300, "write": 500, "live": 2000}


def test_live_delivery_needs_its_p95_and_no_lost_event() -> None:
    delays = [0.1] * 95 + [2.5] * 5  # P95 0.1 s
    verdicts = {v.name: v for v in report.verdicts([], live_delays=delays, live_missing=0)}
    assert verdicts["live"].met and verdicts["live"].value_ms == pytest.approx(100)
    lost = {v.name: v for v in report.verdicts([], live_delays=delays, live_missing=1)}
    assert not lost["live"].met


def test_a_5xx_or_a_transport_error_fails_the_run_and_a_409_does_not() -> None:
    fine = [*_series("ticket_move", [40] * 10), *_series("ticket_move", [40], "409")]
    assert report.verdicts(fine, live_delays=[], live_missing=0)[-1].met
    for status in ("500", "502", "ConnectError"):
        bad = [*fine, *_series("search", [40], status)]
        errors = report.verdicts(bad, live_delays=[], live_missing=0)[-1]
        assert errors.name == "errors" and not errors.met


def test_the_report_names_each_target_and_the_overall_result() -> None:
    samples = [*_series("page_read", [120] * 50), *_series("page_save", [700] * 50)]
    text = report.render(samples, live_delays=[0.2] * 10, live_missing=0, seconds=10.0)
    assert "page_read" in text and "page_save" in text and "live" in text
    assert "MISSED" in text and "overall: MISSED" in text
    met = report.render(samples[:50], live_delays=[0.2], live_missing=0, seconds=10.0)
    assert "overall: MET" in met

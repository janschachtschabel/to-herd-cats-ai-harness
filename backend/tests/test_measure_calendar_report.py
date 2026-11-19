"""The evaluation of the calendar's expansion measurement (plan M10 Task 3c): p50, p95,
queries and work per call, and the verdict against the gate, from a fixed series. The
code is scripts/measure_calendar_report.py; it needs neither a database nor a server."""

import json
from pathlib import Path

import pytest

from scripts import measure_calendar_report as report


def _calls(millis: range | list[int], **fields: int) -> list[report.Call]:
    return [
        report.Call(ms=float(ms), queries=fields.get("queries", 3), **_extra(fields))
        for ms in millis
    ]


def _extra(fields: dict[str, int]) -> dict[str, int]:
    return {k: v for k, v in fields.items() if k != "queries"}


def test_percentile_is_the_nearest_rank() -> None:
    values = [float(v) for v in range(200, 0, -1)]  # 200 … 1, unsorted on purpose
    assert report.percentile(values, 0.50) == 100
    assert report.percentile(values, 0.95) == 190
    assert report.percentile([7.0], 0.95) == 7
    assert report.percentile([1.0, 2.0, 3.0], 0.5) == 2
    with pytest.raises(ValueError):
        report.percentile([], 0.95)


def test_summary_gives_percentiles_queries_and_work_per_call() -> None:
    calls = _calls(range(1, 201), queries=4, work=1000, candidates=200, rows=20, occurrences=50)
    calls[0] = report.Call(ms=1.0, queries=6, work=3000, candidates=400, rows=65, occurrences=50)
    summary = report.summarise("week", calls)
    assert (summary.n, summary.p50_ms, summary.p95_ms, summary.max_ms) == (200, 100, 190, 200)
    assert summary.queries_max == 6
    assert summary.queries_mean == pytest.approx(4.01)
    assert summary.work_mean == pytest.approx(1010)
    assert summary.candidates_mean == pytest.approx(201)
    assert summary.rows_mean == pytest.approx(20.225)
    assert summary.occurrences_mean == 50
    assert summary.errors == 0


def test_summary_without_work_leaves_it_out() -> None:
    summary = report.summarise("week_route", _calls([10, 20, 30]))
    assert summary.work_mean is None and summary.candidates_mean is None
    assert summary.rows_mean is None and summary.occurrences_mean is None


def test_summary_counts_answers_that_are_not_200() -> None:
    calls = [*_calls([10, 20]), report.Call(ms=5.0, queries=2, status=422)]
    assert report.summarise("dense", calls).errors == 1


def test_the_gate_holds_below_300_ms_at_p95() -> None:
    runs = {
        "week": _calls(range(100, 300)),  # p95 289
        "availability_14": _calls(range(50, 250)),  # p95 239
        "week_all_pages": _calls(range(150, 350)),  # p95 339
        "month": _calls(range(500, 700)),  # not gated
    }
    verdicts = report.verdicts({case: report.summarise(case, c) for case, c in runs.items()})
    assert [(v.case, v.p95_ms, v.target_ms, v.met) for v in verdicts] == [
        ("week", 289, 300, True),
        ("availability_14", 239, 300, True),
        ("week_all_pages", 339, 300, False),
    ]
    assert not report.passed(verdicts)  # the whole week (every page) is a target too
    assert report.passed(verdicts[:2])


def test_the_gate_fails_at_300_ms_a_missing_case_or_an_error() -> None:
    at_target = {"week": report.summarise("week", _calls([300] * 200))}
    verdicts = report.verdicts(at_target)
    assert [(v.case, v.met) for v in verdicts] == [
        ("week", False),
        ("availability_14", False),
        ("week_all_pages", False),
    ]
    assert verdicts[1].p95_ms is None  # never measured
    assert not report.passed(verdicts)

    erring = [*_calls([10] * 199), report.Call(ms=10.0, queries=2, status=422)]
    summaries = {
        "week": report.summarise("week", erring),
        "availability_14": report.summarise("availability_14", _calls([10])),
        "week_all_pages": report.summarise("week_all_pages", _calls([40])),
    }
    assert [v.met for v in report.verdicts(summaries)] == [False, True, True]


def test_several_runs_are_judged_each_and_their_spread_shown(tmp_path: Path) -> None:
    def run(path: Path, week_ms: int, load: float) -> Path:
        cases = {
            "week": [{"ms": week_ms, "queries": 3, "work": 900} for _ in range(10)],
            "availability_14": [{"ms": 20, "queries": 2} for _ in range(10)],
            "week_all_pages": [{"ms": 90, "queries": 8} for _ in range(10)],
        }
        path.write_text(json.dumps({"context": {"load_average": load}, "cases": cases}))
        return path

    first, second = run(tmp_path / "a.json", 120, 2.5), run(tmp_path / "b.json", 310, 9.0)
    loaded = [report.load(first), report.load(second)]
    assert loaded[0].context == {"load_average": 2.5}
    assert loaded[0].cases["week"][0] == report.Call(ms=120.0, queries=3, work=900)

    text, ok = report.render(loaded)
    assert not ok  # the second run misses the week's gate
    assert "| week | 1 | 10 | 120.0 | 120.0 |" in text
    assert "| week | 2 | 10 | 310.0 | 310.0 |" in text
    assert "week: p95 120.0–310.0 ms over 2 runs" in text
    assert "load_average 2.5" in text and "load_average 9.0" in text
    assert "FAILED" in text

    assert report.main([str(first)]) == 0
    assert report.main([str(first), str(second)]) == 1

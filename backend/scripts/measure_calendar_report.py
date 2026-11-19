"""The evaluation of the calendar's expansion measurement (plan M10 Task 3c, the gate
for Tasks 4 to 9): per case p50, p95 and max of the calls, queries per call, and the
expansion's counted work, candidates, rows and occurrences per call; the verdict
against the gate.

    uv run python -m scripts.measure_calendar_report RUN.json [RUN.json …]

Gate: the week view (`week`) and the availability load over 14 days
(`availability_14`) at p95 under 300 ms per call, and the whole week with every page
(`week_all_pages`) too, every call answered (status 200), in every run given.
Several runs (repeated because other work shares the machine) are judged each, and
the spread of each case's p95 is shown. Exit 0 when the gate holds.

Pure functions; scripts/measure_calendar.py records, this module judges, and
tests/test_measure_calendar_report.py checks it against a fixed series.
"""

import json
import math
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# The plan's gate (week view and availability over 14 days, per call), and the whole
# week with every page as one more target (the coordinator's, after remedies a and b).
GATES_MS = {"week": 300.0, "availability_14": 300.0, "week_all_pages": 300.0}


@dataclass(frozen=True)
class Call:
    """One call: its duration, the SQL statements it sent, its answer, and what the
    expansion counted (None where the path cannot see it, e.g. through the route)."""

    ms: float
    queries: int
    status: int = 200
    work: int | None = None
    candidates: int | None = None
    rows: int | None = None
    occurrences: int | None = None


@dataclass(frozen=True)
class Summary:
    case: str
    n: int
    p50_ms: float
    p95_ms: float
    max_ms: float
    queries_mean: float
    queries_max: int
    errors: int
    work_mean: float | None
    candidates_mean: float | None
    rows_mean: float | None
    occurrences_mean: float | None


@dataclass(frozen=True)
class Verdict:
    case: str
    p95_ms: float | None  # None: never measured
    target_ms: float
    met: bool


@dataclass(frozen=True)
class Run:
    context: dict[str, Any] = field(default_factory=dict)
    cases: dict[str, list[Call]] = field(default_factory=dict)


def percentile(values: Sequence[float], q: float) -> float:
    """The nearest-rank percentile (q in (0, 1])."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    return ordered[max(math.ceil(q * len(ordered)), 1) - 1]


def _mean(values: Sequence[int | None]) -> float | None:
    known = [v for v in values if v is not None]
    return sum(known) / len(known) if known else None


def summarise(case: str, calls: Sequence[Call]) -> Summary:
    millis = [c.ms for c in calls]
    queries = [c.queries for c in calls]
    return Summary(
        case=case,
        n=len(calls),
        p50_ms=percentile(millis, 0.50),
        p95_ms=percentile(millis, 0.95),
        max_ms=max(millis),
        queries_mean=sum(queries) / len(queries),
        queries_max=max(queries),
        errors=sum(c.status != 200 for c in calls),
        work_mean=_mean([c.work for c in calls]),
        candidates_mean=_mean([c.candidates for c in calls]),
        rows_mean=_mean([c.rows for c in calls]),
        occurrences_mean=_mean([c.occurrences for c in calls]),
    )


def verdicts(summaries: Mapping[str, Summary]) -> list[Verdict]:
    """One per gated case: met when measured, every call answered, p95 under target."""
    found = []
    for case, target in GATES_MS.items():
        summary = summaries.get(case)
        if summary is None:
            found.append(Verdict(case, None, target, False))
            continue
        met = summary.errors == 0 and summary.p95_ms < target
        found.append(Verdict(case, summary.p95_ms, target, met))
    return found


def passed(found: Sequence[Verdict]) -> bool:
    return all(v.met for v in found)


def load(path: Path) -> Run:
    data = json.loads(path.read_text())
    cases = {case: [Call(**call) for call in calls] for case, calls in data["cases"].items()}
    return Run(context=dict(data.get("context", {})), cases=cases)


def _num(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f}"


def render(runs: Sequence[Run]) -> tuple[str, bool]:
    """A Markdown report of the runs and whether every run met the gate."""
    lines = [
        "| case | run | n | p50 ms | p95 ms | max ms | queries Ø/max | work Ø | candidates Ø"
        " | rows Ø | occurrences Ø | not 200 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    p95s: dict[str, list[float]] = {}
    judged: list[tuple[int, Verdict]] = []
    for number, run in enumerate(runs, start=1):
        summaries = {case: summarise(case, calls) for case, calls in run.cases.items()}
        for s in summaries.values():
            p95s.setdefault(s.case, []).append(s.p95_ms)
            lines.append(
                f"| {s.case} | {number} | {s.n} | {s.p50_ms:.1f} | {s.p95_ms:.1f}"
                f" | {s.max_ms:.1f} | {s.queries_mean:.1f}/{s.queries_max}"
                f" | {_num(s.work_mean)} | {_num(s.candidates_mean)} | {_num(s.rows_mean)}"
                f" | {_num(s.occurrences_mean)} | {s.errors} |"
            )
        judged += [(number, v) for v in verdicts(summaries)]
    lines.append("")
    for number, run in enumerate(runs, start=1):
        context = ", ".join(f"{k} {v}" for k, v in sorted(run.context.items()))
        lines.append(f"Run {number}: {context}")
    lines.append("")
    for case, values in p95s.items():
        lines.append(f"{case}: p95 {min(values):.1f}–{max(values):.1f} ms over {len(values)} runs")
    lines.append("")
    for number, v in judged:
        state = "met" if v.met else "FAILED"
        lines.append(
            f"Gate run {number} {v.case}: p95 {_num(v.p95_ms)} < {v.target_ms:.0f} ms {state}"
        )
    ok = all(v.met for _, v in judged)
    lines.append(f"Verdict: {'gate met' if ok else 'gate FAILED'}")
    return "\n".join(lines), ok


def main(argv: Sequence[str]) -> int:
    text, ok = render([load(Path(arg)) for arg in argv])
    print(text)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

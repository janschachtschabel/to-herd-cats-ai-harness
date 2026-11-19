"""The evaluation of the load test (plan M9, decision 20): percentiles per endpoint, the
targets per kind of request, live delivery and errors.

Targets: P95 of every reading endpoint ≤ 300 ms, of every writing endpoint ≤ 500 ms,
live delivery P95 ≤ 2 s with no event lost, no 5xx and no transport error (timeouts,
refused connections). A 4xx (a 409 after a lost race) is counted, but fails nothing.

Pure functions without dependencies; loadmix.py records, this module judges, and
backend/tests/test_loadgen_report.py checks it against a fixed series.
"""

import math
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

KINDS = {
    "page_read": "read",
    "search": "read",
    "board": "read",
    "my_tickets": "read",
    "message_write": "write",
    "ticket_move": "write",
    "page_save": "write",
}
TARGETS_MS = {"read": 300, "write": 500, "live": 2000}


@dataclass(frozen=True)
class Sample:
    """One request: the scenario's endpoint name, its duration and its status (the HTTP
    code as text, or the exception's class name when no answer came)."""

    name: str
    seconds: float
    status: str


@dataclass(frozen=True)
class Summary:
    name: str
    n: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    statuses: dict[str, int]
    client_errors: int
    server_errors: int
    transport_errors: int


@dataclass(frozen=True)
class Verdict:
    name: str
    kind: str
    value_ms: float | None  # P95, or the error count for "errors"
    target_ms: float | None
    met: bool


def percentile(values: Sequence[float], share: float) -> float:
    """The nearest-rank percentile: the smallest value with at least `share` of all
    values at or below it."""
    if not values:
        raise ValueError("no values")
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]


def _is_server_error(status: str) -> bool:
    return status.isdigit() and status.startswith("5")


def summarize(samples: Iterable[Sample]) -> dict[str, Summary]:
    durations: dict[str, list[float]] = {}
    statuses: dict[str, Counter[str]] = {}
    for sample in samples:
        durations.setdefault(sample.name, []).append(sample.seconds * 1000)
        statuses.setdefault(sample.name, Counter())[sample.status] += 1
    result = {}
    for name, ms in durations.items():
        counted = statuses[name]
        result[name] = Summary(
            name=name,
            n=len(ms),
            p50_ms=percentile(ms, 0.50),
            p95_ms=percentile(ms, 0.95),
            p99_ms=percentile(ms, 0.99),
            max_ms=max(ms),
            statuses=dict(counted),
            client_errors=sum(c for s, c in counted.items() if s.isdigit() and s[0] == "4"),
            server_errors=sum(c for s, c in counted.items() if _is_server_error(s)),
            transport_errors=sum(c for s, c in counted.items() if not s.isdigit()),
        )
    return result


def verdicts(
    samples: Sequence[Sample], *, live_delays: Sequence[float], live_missing: int
) -> list[Verdict]:
    """One verdict per endpoint (its P95 against its kind's target), one for live
    delivery (when measured) and, last, one for errors."""
    summaries = summarize(samples)
    result = []
    for name, summary in summaries.items():
        kind = KINDS.get(name, "read")
        target = TARGETS_MS[kind]
        result.append(Verdict(name, kind, summary.p95_ms, target, summary.p95_ms <= target))
    if live_delays or live_missing:
        p95 = percentile([d * 1000 for d in live_delays], 0.95) if live_delays else None
        target = TARGETS_MS["live"]
        met = p95 is not None and p95 <= target and live_missing == 0
        result.append(Verdict("live", "live", p95, target, met))
    failed = sum(s.server_errors + s.transport_errors for s in summaries.values())
    result.append(Verdict("errors", "errors", float(failed), 0.0, failed == 0))
    return result


def render(
    samples: Sequence[Sample],
    *,
    live_delays: Sequence[float],
    live_missing: int,
    seconds: float,
) -> str:
    """The report as text: a line per endpoint, the live delivery, the verdicts."""
    lines = [f"{'endpoint':14} {'n':>6} {'rps':>6} {'p50':>6} {'p95':>6} {'p99':>6} {'max':>7}"]
    for s in summarize(samples).values():
        lines.append(
            f"{s.name:14} {s.n:6} {s.n / seconds:6.1f} {s.p50_ms:6.0f} {s.p95_ms:6.0f}"
            f" {s.p99_ms:6.0f} {s.max_ms:7.0f}  statuses={s.statuses}"
        )
    if live_delays:
        ms = [d * 1000 for d in live_delays]
        lines.append(
            f"{'live':14} {len(ms):6} {'':6} {percentile(ms, 0.5):6.0f}"
            f" {percentile(ms, 0.95):6.0f} {percentile(ms, 0.99):6.0f} {max(ms):7.0f}"
            f"  missing={live_missing}"
        )
    results = verdicts(samples, live_delays=live_delays, live_missing=live_missing)
    lines.append("")
    for v in results:
        value = "-" if v.value_ms is None else f"{v.value_ms:.0f}"
        state = "met" if v.met else "MISSED"
        lines.append(f"target {v.name:14} {v.kind:6} {value:>7} / {v.target_ms:.0f}  {state}")
    lines.append("overall: " + ("MET" if all(v.met for v in results) else "MISSED"))
    return "\n".join(lines)

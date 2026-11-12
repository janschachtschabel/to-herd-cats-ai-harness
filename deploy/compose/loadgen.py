"""Helpers for load.sh: a small load generator (used when neither hey nor oha is
installed) and the summary of `docker stats` samples.

    python loadgen.py run BASE EMAIL PASSWORD CONCURRENCY SECONDS
        CONCURRENCY clients, each in a loop: log in (POST /api/auth/login, its own
        cookie jar), then list spaces (GET /api/spaces?limit=50). Prints requests,
        requests/s, P50/P90/P99/max and status codes per endpoint.

    python loadgen.py stats FILE
        FILE has lines "phase<TAB>container<TAB>cpu%<TAB>mem usage / limit" (docker
        stats --format); prints CPU and memory (avg, max) per phase and container.

Run it with the backend's environment, which has httpx: `uv run --project backend`.
"""

import asyncio
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable

UNITS = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "kB": 1000, "MB": 1000**2}


def _percentile(values: list[float], share: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * len(ordered)))]


Record = Callable[[str, float, str], None]


async def _client(base: str, email: str, password: str, until: float, record: Record) -> None:
    import httpx

    body = {"email": email, "password": password}
    headers = {"X-Requested-With": "herd"}
    async with httpx.AsyncClient(base_url=base, timeout=30) as client:
        while time.monotonic() < until:
            for name in ("login", "spaces"):
                started = time.monotonic()
                try:
                    if name == "login":
                        response = await client.post("/api/auth/login", json=body, headers=headers)
                    else:
                        response = await client.get("/api/spaces", params={"limit": 50})
                    status = str(response.status_code)
                except httpx.HTTPError as exc:
                    status = type(exc).__name__
                record(name, time.monotonic() - started, status)


async def run(base: str, email: str, password: str, concurrency: int, seconds: float) -> None:
    latencies: dict[str, list[float]] = defaultdict(list)
    statuses: dict[str, Counter[str]] = defaultdict(Counter)

    def record(name: str, seconds_taken: float, status: str) -> None:
        latencies[name].append(seconds_taken)
        statuses[name][status] += 1

    started = time.monotonic()
    until = started + seconds
    await asyncio.gather(
        *(_client(base, email, password, until, record) for _ in range(concurrency))
    )
    elapsed = time.monotonic() - started
    print(f"python load generator: {concurrency} clients, {elapsed:.1f} s")
    for name, values in latencies.items():
        ms = [v * 1000 for v in values]
        print(
            f"{name:7} n={len(ms)} rps={len(ms) / elapsed:.1f}"
            f" p50={_percentile(ms, 0.5):.0f}ms p90={_percentile(ms, 0.9):.0f}ms"
            f" p99={_percentile(ms, 0.99):.0f}ms max={max(ms):.0f}ms"
            f" status={dict(statuses[name])}"
        )


def _bytes(text: str) -> float:
    match = re.fullmatch(r"([\d.]+)\s*([A-Za-z]+)", text.strip())
    if not match:
        raise ValueError(f"unknown memory value {text!r}")
    return float(match[1]) * UNITS[match[2]]


def stats(path: str) -> None:
    cpu: dict[tuple[str, str], list[float]] = defaultdict(list)
    mem: dict[tuple[str, str], list[float]] = defaultdict(list)
    with open(path, encoding="utf-8") as lines:
        for line in lines:
            phase, container, cpu_text, mem_text = line.rstrip("\n").split("\t")
            key = (phase, container)
            cpu[key].append(float(cpu_text.rstrip("%")))
            mem[key].append(_bytes(mem_text.split("/")[0]) / 1024**2)
    heads = ("cpu avg", "cpu max", "MiB avg", "MiB max")
    print(f"{'phase':6} {'container':28} {'n':>3} " + " ".join(f"{h:>8}" for h in heads))
    for key in cpu:
        print(
            f"{key[0]:6} {key[1]:28} {len(cpu[key]):3} {statistics.fmean(cpu[key]):7.1f}%"
            f" {max(cpu[key]):7.1f}% {statistics.fmean(mem[key]):8.1f} {max(mem[key]):8.1f}"
        )


if __name__ == "__main__":
    if sys.argv[1:2] == ["run"] and len(sys.argv) == 7:
        _, _, base, email, password, concurrency, seconds = sys.argv
        asyncio.run(run(base, email, password, int(concurrency), float(seconds)))
    elif sys.argv[1:2] == ["stats"] and len(sys.argv) == 3:
        stats(sys.argv[2])
    else:
        sys.exit(__doc__)

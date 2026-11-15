"""The settable clock of the browser tests (plan M7 task 10), and the launcher that
starts the app with it: `python -m tests.support.e2e_clock` in place of
`python -m app.launch` (`e2e/global-setup.mjs`).

Code that schedules reads the time from `app.core.clock.SYSTEM_CLOCK` (the due loop,
the event rules' handler, the automations service, the page review). Here that
clock's `now()` is the system time plus an offset in seconds, read from the file
HERD_E2E_CLOCK_FILE at every call; the harness writes the file (`POST /clock` on its
control port), so a test moves the app's time forward without waiting for a term to
come due. Without the file the offset is 0.

It exists only in the test tree: the image copies `backend/app` and `backend/alembic`,
never `backend/tests` (`tests/test_e2e_clock.py` checks the Dockerfile), and nothing
under `app/` reads the file or knows this module. As a second guard the launcher
refuses to start with HERD_ENVIRONMENT=production.
"""

import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from app.core.clock import SystemClock
from app.core.models_base import utcnow

CLOCK_FILE = "HERD_E2E_CLOCK_FILE"


def offset(path: Path) -> float:
    """The offset in seconds the file holds; 0 without the file."""
    try:
        text = path.read_text().strip()
    except FileNotFoundError:
        return 0.0
    return float(text) if text else 0.0


def install(path: Path) -> Callable[[], None]:
    """Make `SystemClock.now()` the system time plus the file's offset; returns the
    undo (for tests of this module)."""
    original = SystemClock.now

    def now(self: SystemClock) -> datetime:
        return utcnow() + timedelta(seconds=offset(path))

    SystemClock.now = now  # type: ignore[method-assign]

    def undo() -> None:
        SystemClock.now = original  # type: ignore[method-assign]

    return undo


def main() -> None:
    if os.environ.get("HERD_ENVIRONMENT", "development") == "production":
        raise SystemExit("the e2e clock never runs with HERD_ENVIRONMENT=production")
    path = os.environ.get(CLOCK_FILE)
    if not path:
        raise SystemExit(f"{CLOCK_FILE} must name the file of the clock's offset")
    install(Path(path))
    from app.launch import main as launch

    launch()


if __name__ == "__main__":
    main()

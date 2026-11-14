"""The browser tests' settable clock (`tests/support/e2e_clock.py`, plan M7 task 10):
it moves `SYSTEM_CLOCK` by the offset its file holds, and it cannot reach a
production installation: the image never contains the test tree, nothing under
`app/` knows it, and its launcher refuses HERD_ENVIRONMENT=production."""

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.core.clock import SYSTEM_CLOCK
from app.core.models_base import utcnow
from tests.support import e2e_clock

ROOT = Path(__file__).resolve().parents[2]


def test_the_clock_moves_by_the_files_offset_and_back(tmp_path: Path) -> None:
    path = tmp_path / "offset"
    undo = e2e_clock.install(path)
    try:
        assert abs(SYSTEM_CLOCK.now() - utcnow()) < timedelta(seconds=5)  # no file: 0
        path.write_text("86400.5")
        moved = SYSTEM_CLOCK.now() - utcnow()
        assert timedelta(days=1) <= moved < timedelta(days=1, seconds=5)
        path.write_text("0")
        assert abs(SYSTEM_CLOCK.now() - utcnow()) < timedelta(seconds=5)
    finally:
        undo()
    path.write_text("86400")
    assert abs(SYSTEM_CLOCK.now() - utcnow()) < timedelta(seconds=5)  # undone


def test_the_launcher_refuses_production(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERD_ENVIRONMENT", "production")
    monkeypatch.setenv(e2e_clock.CLOCK_FILE, str(tmp_path / "offset"))
    with pytest.raises(SystemExit, match="production"):
        e2e_clock.main()


def test_the_launcher_needs_its_file(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HERD_ENVIRONMENT", "development")
    monkeypatch.delenv(e2e_clock.CLOCK_FILE, raising=False)
    with pytest.raises(SystemExit, match=e2e_clock.CLOCK_FILE):
        e2e_clock.main()


def test_the_image_carries_no_test_code() -> None:
    copied = re.findall(
        r"^COPY\s+(?:--\S+\s+)*(.+?)\s+\S+$", (ROOT / "Dockerfile").read_text(), re.M
    )
    sources = [src for line in copied for src in line.split()]
    assert not {".", "./", "backend", "backend/"} & set(sources), sources  # never the tree
    backend = [src for src in sources if src.startswith("backend")]
    assert backend, "the Dockerfile copies the backend"
    assert all(
        src.startswith(
            ("backend/app", "backend/alembic", "backend/pyproject.toml", "backend/uv.lock")
        )
        for src in backend
    ), backend


def test_nothing_in_the_app_knows_the_e2e_clock() -> None:
    for source in (ROOT / "backend" / "app").rglob("*.py"):
        text = source.read_text()
        assert "e2e_clock" not in text and e2e_clock.CLOCK_FILE not in text, source

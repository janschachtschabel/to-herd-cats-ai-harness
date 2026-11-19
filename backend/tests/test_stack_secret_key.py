"""`python -m app.stack set-secret-key` (M9b Task 19, review R5): puts a saved
HERD_SECRET_KEY back into the Hostinger stack's secrets volume, e.g. on a new VPS
before a restore, since init never replaces a key it finds."""

import io
import os
import stat
from pathlib import Path

import pytest

from app.core.secrets import key_id
from app.stack.init import run_init
from app.stack.secret_key import KEY_FILE, run_set_secret_key

SAVED = "3f" * 32  # what init writes: 64 hex characters


def _set(text: str, secrets_dir: Path) -> tuple[int, str]:
    out = io.StringIO()
    return run_set_secret_key(text, secrets_dir=secrets_dir, out=out), out.getvalue()


async def test_it_replaces_the_key_init_made_and_init_keeps_it(tmp_path: Path) -> None:
    secrets, db_secret = tmp_path / "secrets", tmp_path / "db-secret"
    secrets.mkdir()
    db_secret.mkdir()
    await run_init({}, secrets_dir=secrets, db_secret_dir=db_secret, out=io.StringIO())
    new = (secrets / KEY_FILE).read_text()
    code, out = _set(SAVED + "\n", secrets)  # a pasted line ends with a newline
    assert code == 0
    assert (secrets / KEY_FILE).read_text() == SAVED
    assert stat.S_IMODE(os.stat(secrets / KEY_FILE).st_mode) == 0o400
    assert key_id(SAVED) in out and key_id(new) in out  # which key, which one it replaced
    assert SAVED not in out and new not in out
    await run_init({}, secrets_dir=secrets, db_secret_dir=db_secret, out=io.StringIO())
    assert (secrets / KEY_FILE).read_text() == SAVED  # the next deploy keeps it


def test_the_same_key_again_changes_nothing(tmp_path: Path) -> None:
    _set(SAVED, tmp_path)
    code, out = _set(SAVED, tmp_path)
    assert code == 0 and "unchanged" in out


@pytest.mark.parametrize(
    "text", ["", "\n", "kurz", "3f" * 15, "3f" * 16 + " " + "3f" * 16, "\t" + "3f" * 32]
)
def test_a_key_the_app_would_refuse_writes_nothing(tmp_path: Path, text: str) -> None:
    code, out = _set(text, tmp_path)
    assert code == 2
    assert "HERD_SECRET_KEY" in out and "32" in out
    assert not (tmp_path / KEY_FILE).exists()
    if text.strip():
        assert text.strip() not in out


def test_a_volume_it_cannot_write_is_a_clear_line(tmp_path: Path) -> None:
    missing = tmp_path / "nowhere"
    code, out = _set(SAVED, missing)
    assert code == 1
    assert str(missing) in out and "10001" in out


def test_the_command_line_reads_the_key_from_standard_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.stack.__main__ import main  # noqa: PLC0415 (the entry point under test)

    monkeypatch.setattr("sys.stdin", io.StringIO(SAVED + "\n"))
    assert main(["set-secret-key", "--secrets", str(tmp_path)]) == 0
    assert (tmp_path / KEY_FILE).read_text() == SAVED
    assert key_id(SAVED) in capsys.readouterr().out


def test_a_key_file_it_cannot_read_is_replaced(tmp_path: Path) -> None:
    """init's line for an unusable key file points here (e.g. one copied in by hand)."""
    (tmp_path / KEY_FILE).write_bytes(b"\xff\xfe not text")
    code, out = _set(SAVED, tmp_path)
    assert code == 0
    assert (tmp_path / KEY_FILE).read_text() == SAVED
    assert "unreadable" in out

"""`python -m app.stack init` (plan M9 task 19): the Hostinger stack's first service.

It writes the generated secrets once, checks DOMAIN and the one-time admin values,
and does nothing more while values are missing (exit 0)."""

import io
import os
import stat
from pathlib import Path

import pytest

from app.core.config import Settings
from app.stack.init import DB_PASSWORD, GENERATED, PASSWORD_FILE, run_init

GOOD_PASSWORD = "Zq8!vR2#mLp4-tisch"


@pytest.fixture
def dirs(tmp_path: Path) -> tuple[Path, Path]:
    secrets, db_secret = tmp_path / "secrets", tmp_path / "db-secret"
    secrets.mkdir()
    db_secret.mkdir()
    return secrets, db_secret


async def _init(dirs: tuple[Path, Path], **env: str) -> tuple[int, str]:
    out = io.StringIO()
    code = await run_init(env, secrets_dir=dirs[0], db_secret_dir=dirs[1], out=out)
    return code, out.getvalue()


def _secrets(dirs: tuple[Path, Path]) -> dict[str, str]:
    files = [dirs[1] / DB_PASSWORD, *(dirs[0] / name for name in GENERATED)]
    return {path.name: path.read_text() for path in files}


async def test_a_first_start_without_any_value_writes_the_secrets_and_succeeds(
    dirs: tuple[Path, Path],
) -> None:
    code, out = await _init(dirs)
    assert code == 0
    values = _secrets(dirs)
    assert set(values) == {DB_PASSWORD, *GENERATED}
    assert all(len(v) == 64 and int(v, 16) >= 0 for v in values.values())
    assert len(set(values.values())) == len(values)  # each its own
    assert (dirs[0] / PASSWORD_FILE).read_text() == ""  # no bootstrap
    assert "DOMAIN" in out and "skipped" in out
    for value in values.values():
        assert value not in out  # never printed


async def test_the_secrets_stay_the_same_on_every_later_start(dirs: tuple[Path, Path]) -> None:
    await _init(dirs)
    first = _secrets(dirs)
    code, _ = await _init(dirs, DOMAIN="wiki.example.org")
    assert code == 0
    assert _secrets(dirs) == first


async def test_the_secret_files_are_readable_by_their_owner_only(dirs: tuple[Path, Path]) -> None:
    await _init(dirs, ADMIN_EMAIL="chef@firma.de", ADMIN_PASSWORD=GOOD_PASSWORD)
    for path in [dirs[1] / DB_PASSWORD, dirs[0] / PASSWORD_FILE, *(dirs[0] / n for n in GENERATED)]:
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o400
    assert not [p for p in [*dirs[0].iterdir(), *dirs[1].iterdir()] if p.name.startswith(".")]


async def test_the_files_are_what_the_settings_read(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    await _init(dirs, ADMIN_EMAIL="chef@firma.de", ADMIN_PASSWORD=GOOD_PASSWORD)
    monkeypatch.setenv("HERD_SECRET_KEY_FILE", str(dirs[0] / "secret_key"))
    monkeypatch.setenv("HERD_INTERNAL_TOKEN_FILE", str(dirs[0] / "internal_token"))
    monkeypatch.setenv("HERD_BOOTSTRAP_ADMIN_PASSWORD_FILE", str(dirs[0] / PASSWORD_FILE))
    monkeypatch.setenv("HERD_DATABASE_PASSWORD_FILE", str(dirs[1] / DB_PASSWORD))
    settings = Settings()
    assert settings.bootstrap_admin_password.get_secret_value() == GOOD_PASSWORD
    assert settings.internal_token is not None and settings.secret_key is not None
    assert settings.database().password == (dirs[1] / DB_PASSWORD).read_text()


@pytest.mark.parametrize(
    "domain",
    [
        "https://wiki.example.org",
        "wiki.example.org/",
        "wiki.example.org:443",
        " wiki.example.org",
        "wiki example.org",
        "-wiki.example.org",
        "wiki..example.org",
        "wiki.example.org.",
        "x" * 64 + ".example.org",
    ],
)
async def test_a_domain_that_is_not_a_bare_host_name_stops_the_start(
    dirs: tuple[Path, Path], domain: str
) -> None:
    code, out = await _init(dirs, DOMAIN=domain)
    assert code == 2
    assert "DOMAIN" in out and "wiki.example.org" in out and "https://" in out


@pytest.mark.parametrize(
    "domain", ["wiki.example.org", "srv123456.hstgr.cloud", "xn--mller-kva.de", "a-1.b2.io"]
)
async def test_a_bare_host_name_is_taken(dirs: tuple[Path, Path], domain: str) -> None:
    code, out = await _init(dirs, DOMAIN=domain)
    assert code == 0
    assert domain in out


async def test_a_domain_with_capitals_is_refused_not_lowered(dirs: tuple[Path, Path]) -> None:
    """A browser sends the Origin in lower case, and the live editing compares it with
    https://DOMAIN exactly: Wiki.Example.org would route but never connect live."""
    code, out = await _init(dirs, DOMAIN="Wiki.Example.ORG")
    assert code == 2
    assert "'Wiki.Example.ORG'" in out and "wiki.example.org" in out  # names the fix
    assert "klein" in out


@pytest.mark.parametrize("domain", ["203.0.113.5", "10.0.0.1"])
async def test_an_ip_address_is_refused(dirs: tuple[Path, Path], domain: str) -> None:
    """Traefik's HTTP challenge gets no certificate for an IP address."""
    code, out = await _init(dirs, DOMAIN=domain)
    assert code == 2
    assert domain in out and "IP" in out and "hstgr.cloud" in out


@pytest.mark.parametrize("domain", ["localhost", "wiki"])
async def test_a_name_without_a_dot_is_refused(dirs: tuple[Path, Path], domain: str) -> None:
    code, out = await _init(dirs, DOMAIN=domain)
    assert code == 2
    assert repr(domain) in out and "wiki.example.org" in out


async def test_an_umlaut_domain_is_refused_with_its_ace_form(dirs: tuple[Path, Path]) -> None:
    code, out = await _init(dirs, DOMAIN="wiki.müller.de")
    assert code == 2
    assert "xn--" in out and "wiki.xn--mller-kva.de" in out


async def test_the_admin_password_is_written_for_the_app_and_emptied_once_cleared(
    dirs: tuple[Path, Path],
) -> None:
    code, out = await _init(dirs, ADMIN_EMAIL="chef@firma.de", ADMIN_PASSWORD=GOOD_PASSWORD)
    assert code == 0
    assert (dirs[0] / PASSWORD_FILE).read_text() == GOOD_PASSWORD
    assert GOOD_PASSWORD not in out
    code, out = await _init(dirs, ADMIN_EMAIL="chef@firma.de")
    assert code == 0
    assert (dirs[0] / PASSWORD_FILE).read_text() == ""
    assert "ADMIN_PASSWORD" in out


@pytest.mark.parametrize(
    ("env", "named"),
    [
        ({"ADMIN_PASSWORD": GOOD_PASSWORD}, "ADMIN_EMAIL"),
        ({"ADMIN_EMAIL": "chef", "ADMIN_PASSWORD": GOOD_PASSWORD}, "ADMIN_EMAIL"),
        ({"ADMIN_EMAIL": "chef@firma.de", "ADMIN_PASSWORD": "kurz"}, "ADMIN_PASSWORD"),
        # On the list of breached passwords, or holding a word of the address.
        ({"ADMIN_EMAIL": "chef@firma.de", "ADMIN_PASSWORD": "password1234"}, "ADMIN_PASSWORD"),
        ({"ADMIN_EMAIL": "chef@firma.de", "ADMIN_PASSWORD": "firma-9!xQ2#"}, "ADMIN_PASSWORD"),
    ],
)
async def test_admin_values_the_app_would_refuse_stop_the_start(
    dirs: tuple[Path, Path], env: dict[str, str], named: str
) -> None:
    code, out = await _init(dirs, **env)
    assert code == 2
    assert named in out
    assert env["ADMIN_PASSWORD"] not in out
    assert not (dirs[0] / PASSWORD_FILE).exists()  # nothing for the app to use


async def test_an_empty_secret_file_is_a_broken_volume_not_regenerated(
    dirs: tuple[Path, Path],
) -> None:
    """A new database password would lock the app out of the existing database."""
    await _init(dirs)
    path = dirs[1] / DB_PASSWORD
    path.chmod(0o600)
    path.write_text("")
    code, out = await _init(dirs)
    assert code == 1
    assert DB_PASSWORD in out
    assert path.read_text() == ""


async def test_a_secret_file_it_cannot_read_is_a_clear_line_not_a_traceback(
    dirs: tuple[Path, Path],
) -> None:
    """E.g. a key copied in by hand as root with mode 0600: init runs as 10001."""
    (dirs[0] / "secret_key").mkdir()  # unreadable as a file, also for root
    code, out = await _init(dirs)
    assert code == 1
    assert "secret_key" in out and "10001" in out and "set-secret-key" in out


def test_the_command_line_runs_it_with_the_environment(
    dirs: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from app.stack.__main__ import main  # noqa: PLC0415 (the entry point under test)

    monkeypatch.setenv("DOMAIN", "https://wiki.example.org")
    argv = ["init", "--secrets", str(dirs[0]), "--db-secret", str(dirs[1])]
    assert main(argv) == 2
    monkeypatch.setenv("DOMAIN", "wiki.example.org")
    assert main(argv) == 0
    assert "secrets ready (3 created, 0 kept)" in capsys.readouterr().out

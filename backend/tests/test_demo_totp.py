"""The demo's second factor (scripts/demo_totp.py, M9b): only with `--totp-file` Ben
sets up TOTP through the profile's API, and his key and recovery codes go into a new
file only he may read; then password and code (or a recovery code) open his session.
Without the file nobody has TOTP. An existing file is never overwritten."""

import stat
from collections.abc import Awaitable, Callable
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient

from scripts import demo_totp
from scripts.demo_api import DemoFailed
from scripts.demo_seed import main
from tests.factories import CSRF, PASSWORD, MakeUser, login
from tests.support.clock import SettableClock
from tests.test_demo_seed import demo  # noqa: F401 -- the fixture

TOTP = "/api/auth/me/totp"
SECOND = "/api/auth/login/second-factor"


async def test_without_a_file_nobody_has_totp(demo: dict[str, Any]) -> None:  # noqa: F811
    assert demo["seeded"].totp.enabled_for is None
    ben = demo["clients"]["ben"]
    status = (await ben.get(TOTP)).json()
    assert status["enabled_at"] is None


def _read(path: Path) -> tuple[str, list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    key = next(line.removeprefix("key: ") for line in lines if line.startswith("key: "))
    codes = lines[lines.index("recovery codes:") + 1 :]
    return key, codes


async def test_with_a_file_ben_signs_in_with_password_and_a_code(
    make_client: Callable[..., Awaitable[AsyncClient]],
    make_user: MakeUser,
    totp_time: SettableClock,
    tmp_path: Path,
) -> None:
    ben = await make_user(email="ben.berg@demo.example", name="Ben Berg")
    browser = await make_client(csrf=True)
    await login(browser, ben.email, PASSWORD)
    path = tmp_path / "ben-totp.txt"
    seeded = await demo_totp.build(
        browser,
        key="ben",
        email=ben.email,
        password=PASSWORD,
        totp_file=path,
        now=lambda: totp_time.now().timestamp(),
    )
    assert seeded.enabled_for == "ben"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    key, codes = _read(path)
    assert len(codes) == 10
    assert key not in repr(seeded)
    assert (await browser.get(TOTP)).json()["enabled_at"] is not None

    phone = await make_client()
    first = await phone.post(
        "/api/auth/login", json={"email": ben.email, "password": PASSWORD}, headers=CSRF
    )
    assert (first.status_code, first.json()["second_factor"]) == (202, "totp")
    totp_time.advance(timedelta(seconds=demo_totp.STEP_SECONDS))  # the first step is spent
    code = demo_totp.code_at(key, totp_time.now().timestamp())
    second = await phone.post(SECOND, json={"code": code}, headers=CSRF)
    assert second.status_code == 200, second.text

    laptop = await make_client()
    await laptop.post(
        "/api/auth/login", json={"email": ben.email, "password": PASSWORD}, headers=CSRF
    )
    recovered = await laptop.post(SECOND, json={"recovery_code": codes[0]}, headers=CSRF)
    assert recovered.status_code == 200, recovered.text


async def test_an_existing_file_is_never_overwritten_and_totp_stays_off(
    make_client: Callable[..., Awaitable[AsyncClient]],
    make_user: MakeUser,
    totp_time: SettableClock,
    tmp_path: Path,
) -> None:
    ben = await make_user(email="ben.berg@demo.example")
    browser = await make_client(csrf=True)
    await login(browser, ben.email, PASSWORD)
    path = tmp_path / "ben-totp.txt"
    path.write_text("mine\n", encoding="utf-8")
    with pytest.raises(DemoFailed):
        await demo_totp.build(
            browser, key="ben", email=ben.email, password=PASSWORD, totp_file=path
        )
    assert path.read_text(encoding="utf-8") == "mine\n"
    assert (await browser.get(TOTP)).json()["enabled_at"] is None


async def test_a_refused_setup_leaves_no_file(
    make_client: Callable[..., Awaitable[AsyncClient]],
    make_user: MakeUser,
    totp_time: SettableClock,
    tmp_path: Path,
) -> None:
    ben = await make_user(email="ben.berg@demo.example")
    browser = await make_client(csrf=True)
    await login(browser, ben.email, PASSWORD)
    path = tmp_path / "ben-totp.txt"
    with pytest.raises(DemoFailed):
        await demo_totp.build(
            browser, key="ben", email=ben.email, password="not-" + PASSWORD, totp_file=path
        )
    assert not path.exists()


def test_the_codes_follow_rfc_6238() -> None:
    # RFC 6238, appendix B, SHA-1 (the secret "12345678901234567890"), last six digits
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"
    assert demo_totp.code_at(secret, 59) == "287082"
    assert demo_totp.code_at(secret, 1111111109) == "081804"
    assert demo_totp.code_at(secret, 20000000000) == "353130"


def test_the_seed_takes_a_totp_file_by_argument(
    monkeypatch: Any, tmp_path: Path, capsys: Any
) -> None:
    seen: dict[str, Any] = {}

    async def fake_main(*args: Any) -> int:
        seen["totp_file"] = args[4]
        return 0

    monkeypatch.setattr("scripts.demo_seed._main", fake_main)
    path = tmp_path / "ben-totp.txt"
    assert main(["--admin", "a@example.com", "--totp-file", str(path)]) == 0
    assert seen["totp_file"] == path
    assert main(["--admin", "a@example.com"]) == 0
    assert seen["totp_file"] is None
    path.write_text("mine\n", encoding="utf-8")
    seen.clear()
    assert main(["--admin", "a@example.com", "--totp-file", str(path)]) == 2
    assert seen == {} and "exists already" in capsys.readouterr().out

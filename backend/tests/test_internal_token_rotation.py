"""Rotating the internal token without an outage (plan M9 task 18, J12 c; ASVS 5.0
V13.2.1): the API takes HERD_INTERNAL_TOKEN and, while a rotation runs,
HERD_INTERNAL_TOKEN_PREVIOUS; the collab process sends only the current one."""

from pathlib import Path

import pytest
from httpx import AsyncClient
from pydantic import SecretStr, ValidationError

from app.core.config import Settings, get_settings
from tests.factories_collab import HEADER, TOKEN, expect_error

NEW = "n" * 40
BODY = {"grant": "x", "page_id": "01a1d2d9-2de5-75db-9dc6-a6fa1307273d", "generation": 0}


async def _status(internal: AsyncClient, token: str | None) -> str:
    headers = {HEADER: token} if token is not None else {}
    r = await internal.post("/internal/collab/auth", json=BODY, headers=headers)
    return r.json()["error"]["code"]


async def test_both_internal_tokens_are_accepted(
    internal: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "internal_token", SecretStr(NEW))
    monkeypatch.setattr(settings, "internal_token_previous", SecretStr(TOKEN))
    # Past the token check, the made-up grant is what fails: both tokens pass.
    assert await _status(internal, NEW) == "collab.grant_invalid"
    assert await _status(internal, TOKEN) == "collab.grant_invalid"
    for wrong in (None, "wrong", NEW[:-1], TOKEN + "x", ""):
        assert await _status(internal, wrong) == "internal.unauthorized"
    # The rotation ended: the old token is refused again.
    monkeypatch.setattr(settings, "internal_token_previous", None)
    r = await internal.post("/internal/collab/auth", json=BODY, headers={HEADER: TOKEN})
    expect_error(r, 401, "internal.unauthorized")
    assert await _status(internal, NEW) == "collab.grant_invalid"


def test_the_previous_token_follows_the_tokens_rules(tmp_path: Path) -> None:
    with pytest.raises(ValidationError):
        Settings(internal_token=SecretStr(NEW), internal_token_previous=SecretStr("short"))
    assert Settings(internal_token_previous=SecretStr("")).internal_token_previous is None
    path = tmp_path / "previous"
    path.write_text(TOKEN + "\n", encoding="utf-8")
    loaded = Settings(internal_token=SecretStr(NEW), internal_token_previous_file=path)
    assert loaded.internal_token_previous is not None
    assert loaded.internal_token_previous.get_secret_value() == TOKEN
    assert TOKEN not in repr(loaded)

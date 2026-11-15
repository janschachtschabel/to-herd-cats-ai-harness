"""The cap on automations per person (plan M7 decision 12): `HERD_AI_AUTOMATIONS_MAX`,
default 20, read by the API; a reserved `HERD_AI_` name no `env:` key may reference."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.secrets import RESERVED_NAMES, env_ref


def test_the_cap_defaults_to_twenty_and_reads_its_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().ai_automations_max == 20
    monkeypatch.setenv("HERD_AI_AUTOMATIONS_MAX", "3")
    assert Settings().ai_automations_max == 3


def test_the_cap_stays_within_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("-1", "1001"):
        monkeypatch.setenv("HERD_AI_AUTOMATIONS_MAX", value)
        with pytest.raises(ValidationError):
            Settings()


def test_no_key_may_reference_the_cap() -> None:
    assert "HERD_AI_AUTOMATIONS_MAX" in RESERVED_NAMES
    with pytest.raises(ValidationFailed):
        env_ref("HERD_AI_AUTOMATIONS_MAX")

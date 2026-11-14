"""Secret references (plan M5 decision 6): `env:NAME` and `enc:<ciphertext>`; the
plaintext appears only when resolved for a call, never in a repr, message or log."""

import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.config import Settings, get_settings
from app.core.errors import ValidationFailed
from app.modules.ai.models import AiConnection
from app.modules.ai.secret_rotation import RotationFailed, rotate_secrets
from app.modules.orgs.models import Organization

KEY = "k" * 40
OTHER_KEY = "o" * 40
PLAIN = "sk-test-0123456789-very-secret"


@pytest.fixture
def secret_key(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(KEY))
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)
    return KEY


def test_encrypted_reference_round_trips_and_hides_the_value(secret_key: str) -> None:
    ref = secrets.encrypt(PLAIN)
    assert ref.startswith("enc:") and PLAIN not in ref
    assert secrets.kind_of(ref) == secrets.SecretKind.ENC
    resolved = secrets.resolve(ref)
    assert resolved.get_secret_value() == PLAIN
    assert PLAIN not in repr(resolved) and PLAIN not in str(resolved)


def test_two_encryptions_differ(secret_key: str) -> None:
    assert secrets.encrypt(PLAIN) != secrets.encrypt(PLAIN)


def test_without_a_key_only_env_references_work(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", None)
    with pytest.raises(ValidationFailed) as caught:
        secrets.encrypt(PLAIN)
    assert caught.value.code == "secrets.key_missing"
    monkeypatch.setenv("HERD_AI_KEY_ONE", PLAIN)
    assert secrets.resolve("env:HERD_AI_KEY_ONE").get_secret_value() == PLAIN


def test_env_references_are_limited_to_the_ai_prefix() -> None:
    """An admin must not point a connection at the database password or the secret key
    and send it to a URL of their choosing."""
    assert secrets.env_ref("HERD_AI_OPENAI") == "env:HERD_AI_OPENAI"
    names = ("HERD_DATABASE_PASSWORD", "HERD_SECRET_KEY", "PATH", "HERD_AI_", "herd_ai_x")
    for name in (*names, "HERD_AI_EGRESS_PROXY", "HERD_AI_CHECK_TIMEOUT_SECONDS"):
        with pytest.raises(ValidationFailed) as caught:
            secrets.env_ref(name)
        assert caught.value.code == "secrets.env_name_invalid"


def test_no_own_ai_setting_can_be_a_key_reference() -> None:
    """Every setting of the app with the `HERD_AI_` prefix is refused as a key, the
    ones added after M5 (approval hours, personal-agent limit) included."""
    own = [f"HERD_{name.upper()}" for name in Settings.model_fields if name.startswith("ai_")]
    assert {"HERD_AI_APPROVAL_HOURS", "HERD_AI_PERSONAL_AGENTS_MAX"} <= set(own)
    for name in own:
        with pytest.raises(ValidationFailed) as caught:
            secrets.env_ref(name)
        assert caught.value.code == "secrets.env_name_invalid"


def test_resolving_a_disallowed_or_unset_env_reference_fails_without_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HERD_DATABASE_PASSWORD", PLAIN)
    monkeypatch.setenv("HERD_AI_EGRESS_PROXY", f"http://user:{PLAIN}@proxy:3128")
    refs = ("env:HERD_DATABASE_PASSWORD", "env:HERD_AI_EGRESS_PROXY", "env:HERD_AI_UNSET_X")
    for ref in (*refs, "plain", "enc:"):
        with pytest.raises(secrets.SecretUnavailable) as caught:
            secrets.resolve(ref)
        assert PLAIN not in str(caught.value) and caught.value.__context__ is None


def test_a_wrong_key_does_not_decrypt(secret_key: str, monkeypatch: pytest.MonkeyPatch) -> None:
    ref = secrets.encrypt(PLAIN)
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(OTHER_KEY))
    with pytest.raises(secrets.SecretUnavailable) as caught:
        secrets.resolve(ref)
    assert caught.value.__cause__ is None and caught.value.__context__ is None
    assert PLAIN not in str(caught.value)


def test_rotation_reencrypts_under_the_new_key(
    secret_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_ref = secrets.encrypt(PLAIN)
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(OTHER_KEY))
    monkeypatch.setattr(get_settings(), "secret_key_previous", SecretStr(KEY))
    assert secrets.resolve(old_ref).get_secret_value() == PLAIN  # still readable
    new_ref = secrets.rotate(old_ref)
    assert new_ref != old_ref
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)
    assert secrets.resolve(new_ref).get_secret_value() == PLAIN
    with pytest.raises(secrets.SecretUnavailable):
        secrets.resolve(old_ref)
    assert secrets.rotate("env:HERD_AI_X") == "env:HERD_AI_X"


def test_plaintext_values_are_checked(secret_key: str) -> None:
    for bad in ("", "a b", "line\nbreak", "x" * 5000, "ümlaut"):
        with pytest.raises(ValidationFailed) as caught:
            secrets.encrypt(bad)
        assert caught.value.code == "secrets.value_invalid"


def test_short_secret_keys_are_refused_at_start() -> None:
    with pytest.raises(ValidationError) as caught:
        Settings(secret_key=SecretStr("short"))
    assert "short" not in str(caught.value)
    assert Settings(secret_key=SecretStr("")).secret_key is None
    with pytest.raises(ValidationError):
        Settings(secret_key=SecretStr(KEY), secret_key_previous=SecretStr("short"))


async def test_stored_secrets_are_rotated_all_or_nothing(
    session: AsyncSession, org: Organization, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(KEY))
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)
    row = AiConnection(
        org_id=org.id,
        name="A",
        kind="openai",
        base_url="https://api.openai.com/v1",
        secret_ref=secrets.encrypt(PLAIN),
        models=[],
        param_family="max_tokens",
        extra_body={},
        data_location="external",
        purpose="chat",
    )
    session.add(row)
    await session.flush()
    old_ref = row.secret_ref
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr(OTHER_KEY))
    monkeypatch.setattr(get_settings(), "secret_key_previous", SecretStr(KEY))
    assert await rotate_secrets(session) == 1
    assert row.secret_ref != old_ref and row.secret_ref is not None
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)
    assert secrets.resolve(row.secret_ref).get_secret_value() == PLAIN
    row.secret_ref = old_ref  # under a key no longer known
    await session.flush()
    with pytest.raises(RotationFailed) as caught:
        await rotate_secrets(session)
    assert caught.value.connection_id == row.id and PLAIN not in str(caught.value)

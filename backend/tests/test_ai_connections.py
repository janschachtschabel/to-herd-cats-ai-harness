"""AI connections (spec 7.1): admins set them up; everyone else learns nothing (404);
a secret goes in, never comes out (answers, audit, logs)."""

import json
from typing import Any

import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.config import get_settings
from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.principal import Principal, SystemRole
from app.modules.ai.connections import ConnectionService
from app.modules.ai.models import AiConnection
from app.modules.audit.models import AuditLog
from app.modules.orgs.models import Organization
from tests.factories import MakeUser, login

BASE = "/api/ai/connections"
KEY = "sk-live-THE-SECRET-VALUE-1234567890"


@pytest.fixture
def secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", SecretStr("s" * 48))
    monkeypatch.setattr(get_settings(), "secret_key_previous", None)


async def create(client: AsyncClient, **fields: Any) -> dict[str, Any]:
    body = {"name": "OpenAI", **fields}
    response = await client.post(BASE, json=body)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def test_defaults_follow_the_kind(owner: AsyncClient) -> None:
    openai = await create(owner)
    assert openai["base_url"] == "https://api.openai.com/v1"
    assert openai["models"] == ["gpt-6-luna"]
    assert openai["param_family"] == "max_completion_tokens"
    assert openai["data_location"] == "external" and openai["purpose"] == "chat"
    assert openai["streaming"] is True and openai["secret"] == {"set": False, "kind": None}
    local = await create(owner, name="Ollama", kind="local", base_url="http://127.0.0.1:11434/v1")
    assert local["models"] == [] and local["param_family"] == "max_tokens"
    assert local["data_location"] == "local"
    b_api = await create(
        owner, name="B", kind="b_api", base_url="https://b-api.example/v1", models=["route-a"]
    )
    assert b_api["streaming"] is False and b_api["models"] == ["route-a"]


async def test_only_ai_managers_reach_connections(
    owner: AsyncClient,
    make_user: MakeUser,
    make_client: Any,
    member_client: AsyncClient,
    guest_client: AsyncClient,
) -> None:
    admin = await make_user(SystemRole.ADMIN)
    admin_client = await make_client(csrf=True)
    await login(admin_client, admin.email)
    made = await create(admin_client)
    assert (await owner.get(BASE)).json()["items"][0]["id"] == made["id"]
    for client in (member_client, guest_client):
        for method, path, body in (
            ("GET", BASE, None),
            ("POST", BASE, {"name": "X"}),
            ("GET", f"{BASE}/{made['id']}", None),
            ("PATCH", f"{BASE}/{made['id']}", {"name": "Y", "version": 1}),
            ("DELETE", f"{BASE}/{made['id']}?version=1", None),
            ("POST", f"{BASE}/{made['id']}/test", {}),
            ("POST", f"{BASE}/{made['id']}/models", {"version": 1}),
        ):
            response = await client.request(method, path, json=body)
            assert response.status_code == 404, (method, path, response.text)
            assert response.json()["error"]["code"] == "ai.not_found"


async def test_a_secret_value_is_stored_encrypted_and_never_shown(
    owner: AsyncClient, session: AsyncSession, secret_key: None, capsys: pytest.CaptureFixture[str]
) -> None:
    made = await create(owner, secret={"value": KEY})
    assert made["secret"] == {"set": True, "kind": "enc"}
    fetched = await owner.get(f"{BASE}/{made['id']}")
    listed = await owner.get(BASE)
    row = await session.get(AiConnection, made["id"])
    assert row is not None and row.secret_ref is not None
    assert row.secret_ref.startswith("enc:") and KEY not in row.secret_ref
    audit = (await session.scalars(select(AuditLog))).all()
    assert any(a.action == "ai_connection.created" for a in audit)
    texts = [fetched.text, listed.text, json.dumps([a.details for a in audit])]
    texts.append(capsys.readouterr().out)
    assert all(KEY not in text for text in texts)


async def test_without_a_secret_key_only_env_references_are_accepted(
    owner: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "secret_key", None)
    response = await owner.post(BASE, json={"name": "X", "secret": {"value": KEY}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "secrets.key_missing"
    assert KEY not in response.text
    made = await create(owner, secret={"env": "HERD_AI_OPENAI_KEY"})
    assert made["secret"] == {"set": True, "kind": "env"}
    bad = await owner.post(BASE, json={"name": "Y", "secret": {"env": "HERD_DATABASE_PASSWORD"}})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "secrets.env_name_invalid"
    both = await owner.post(BASE, json={"name": "Z", "secret": {"env": "HERD_AI_A", "value": KEY}})
    assert both.status_code == 422 and KEY not in both.text


async def test_invalid_secret_values_are_refused_without_echo(
    owner: AsyncClient, secret_key: None
) -> None:
    for value in ("has space " + KEY, KEY + "\n", "x" * 5000):
        response = await owner.post(BASE, json={"name": "X", "secret": {"value": value}})
        assert response.status_code == 422
        assert value.strip() not in response.text


async def test_update_replaces_or_removes_the_secret_and_audits_only_its_kind(
    owner: AsyncClient, session: AsyncSession, secret_key: None
) -> None:
    made = await create(owner, secret={"env": "HERD_AI_ONE"})
    path = f"{BASE}/{made['id']}"
    replaced = await owner.patch(path, json={"secret": {"value": KEY}, "version": 1})
    assert replaced.status_code == 200 and replaced.json()["secret"]["kind"] == "enc"
    renamed = await owner.patch(path, json={"name": "Neu", "version": 2})
    assert renamed.json()["secret"] == {"set": True, "kind": "enc"}  # untouched
    removed = await owner.patch(path, json={"secret": None, "version": 3})
    assert removed.json()["secret"] == {"set": False, "kind": None}
    rows = (
        await session.scalars(select(AuditLog).where(AuditLog.action == "ai_connection.updated"))
    ).all()
    assert [r.details.get("secret", "-") for r in rows if r.details] == ["enc", "-", None]
    assert KEY not in json.dumps([r.details for r in rows])


async def test_writes_name_the_version_they_read(owner: AsyncClient) -> None:
    made = await create(owner)
    path = f"{BASE}/{made['id']}"
    assert (await owner.patch(path, json={"enabled": False, "version": 1})).status_code == 200
    stale = await owner.patch(path, json={"enabled": True, "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "ai.connection_version_conflict"
    assert stale.json()["error"]["details"] == {"current_version": 2}
    assert (await owner.delete(f"{path}?version=1")).status_code == 409
    assert (await owner.delete(f"{path}?version=2")).status_code == 204
    gone = await owner.get(path)
    assert gone.status_code == 404 and gone.json()["error"]["code"] == "ai.connection_not_found"


async def test_names_are_unique_ignoring_case(owner: AsyncClient) -> None:
    await create(owner, name="OpenAI")
    again = await owner.post(BASE, json={"name": "openai"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "ai.connection_name_taken"
    other = await create(owner, name="Zweite")
    clash = await owner.patch(f"{BASE}/{other['id']}", json={"name": "OPENAI", "version": 1})
    assert clash.status_code == 409


async def test_fields_are_validated(owner: AsyncClient) -> None:
    made = await create(owner)
    path = f"{BASE}/{made['id']}"
    for body in (
        {"name": "X", "extra_body": {"model": "other"}},  # reserved
        {"name": "X", "extra_body": {"stream": True}},
        {"name": "X", "extra_body": {"api_key": "x"}},  # secrets go into `secret`
        {"name": "X", "extra_body": {"x": "y" * 5000}},
        {"name": "X", "models": ["a"] * 2 + [""]},
        {"name": "X", "max_concurrency": 0},
        {"name": "X", "kind": "other"},
        {"name": "X", "org_id": made["id"]},
    ):
        assert (await owner.post(BASE, json=body)).status_code == 422, body
    for body in (
        {"kind": "local", "version": 1},  # the kind never changes
        {"enabled": None, "version": 1},
        {"version": 1, "id": made["id"]},
    ):
        assert (await owner.patch(path, json=body)).status_code == 422, body
    reasoning = await owner.patch(
        path, json={"extra_body": {"reasoning_effort": "none"}, "models": ["a", "b"], "version": 1}
    )
    assert reasoning.json()["extra_body"] == {"reasoning_effort": "none"}
    assert reasoning.json()["models"] == ["a", "b"]


@pytest.mark.parametrize(
    ("kind", "url"),
    [
        ("openai", "http://api.example.com/v1"),
        ("openai", "https://169.254.169.254/v1"),
        ("openai", "https://10.1.2.3/v1"),
        ("openai_compatible", "https://[::ffff:127.0.0.1]/v1"),
        ("openai", "https://user:pw@api.example.com/v1"),
        ("openai", "https://api.example.com/v1?key=x"),
        ("b_api", "https://localhost/v1"),
        ("local", "http://169.254.169.254/v1"),
        ("local", "file:///etc/passwd"),
    ],
)
async def test_base_urls_pass_the_egress_rules_of_their_kind(
    owner: AsyncClient, kind: str, url: str
) -> None:
    response = await owner.post(BASE, json={"name": "X", "kind": kind, "base_url": url})
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "ai.base_url_not_allowed"
    made = await create(owner, name="Y", kind="local", base_url="http://10.1.2.3:8000/v1/")
    assert made["base_url"] == "http://10.1.2.3:8000/v1"
    blocked = await owner.patch(
        f"{BASE}/{made['id']}", json={"base_url": "http://169.254.169.254", "version": 1}
    )
    assert blocked.status_code == 422


async def test_lists_are_paginated(owner: AsyncClient) -> None:
    for i in range(3):
        await create(owner, name=f"C{i}")
    first = (await owner.get(BASE, params={"limit": 2})).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = (await owner.get(BASE, params={"limit": 2, "cursor": first["next_cursor"]})).json()
    assert [c["name"] for c in rest["items"]] == ["C2"] and rest["next_cursor"] is None
    assert (await owner.get(BASE, params={"limit": 101})).status_code == 422


async def test_connections_of_another_organisation_do_not_exist(
    owner: AsyncClient, make_user: MakeUser, session: AsyncSession
) -> None:
    other_org = Organization(name="Other")
    session.add(other_org)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other_org)
    actor = Actor(other_org.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    made = await create(owner)
    service = ConnectionService(session)
    with pytest.raises(NotFound):
        await service.get(actor, made["id"])
    assert (await service.list(actor, PageParams())).items == []

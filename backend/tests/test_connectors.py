"""Connectors (plan M8 decision 9, task 5): stored credentials for external servers.
Shared ones belong to the organisation (`ai.manage`), personal ones to one person
(with `ai.use`), seen and changed by that person alone. A secret goes in and never
comes out: not in answers, audit or logs."""

import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.errors import NotFound
from app.core.pagination import PageParams
from app.core.principal import Principal, SystemRole
from app.modules.audit.models import AuditLog
from app.modules.connectors.models import Connector, ConnectorScope
from app.modules.connectors.service import ConnectorService
from app.modules.orgs.models import Organization
from tests.factories import MakeUser
from tests.factories_connectors import PERSONAL, SHARED, make_connector
from tests.factories_dms import People

KEY = "ghp-THE-SECRET-VALUE-1234567890"


async def test_only_ai_managers_reach_shared_connectors(ai_people: People) -> None:
    made = await make_connector(ai_people.admin)
    path = f"{SHARED}/{made['id']}"
    for who in ("alice", "gast"):
        client = getattr(ai_people, who)
        for method, url, body in (
            ("GET", SHARED, None),
            ("POST", SHARED, {"name": "X", "auth_kind": "bearer", "secret": {"value": "x"}}),
            ("GET", path, None),
            ("PATCH", path, {"name": "Y", "version": 1}),
            ("DELETE", f"{path}?version=1", None),
        ):
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (method, url, response.text)
            assert response.json()["error"]["code"] == "ai.not_found"


async def test_a_secret_is_write_only_everywhere(
    ai_people: People, session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    shared = await make_connector(ai_people.admin, secret={"value": KEY})
    personal = await make_connector(ai_people.alice, PERSONAL, secret={"value": KEY})
    assert shared["has_secret"] is True and shared["secret_kind"] == "enc"
    assert personal["has_secret"] is True and "secret" not in personal
    answers = [
        (await ai_people.admin.get(SHARED)).text,
        (await ai_people.admin.get(f"{SHARED}/{shared['id']}")).text,
        (await ai_people.alice.get(PERSONAL)).text,
        (await ai_people.alice.get(f"{PERSONAL}/{personal['id']}")).text,
    ]
    rows = (await session.scalars(select(Connector))).all()
    assert all(r.secret_ref.startswith("enc:") and KEY not in r.secret_ref for r in rows)
    audit = (await session.scalars(select(AuditLog))).all()
    assert {"connector.created"} <= {a.action for a in audit}
    texts = [*answers, json.dumps([a.details for a in audit]), capsys.readouterr().out]
    assert all(KEY not in text for text in texts)


async def test_header_connectors_name_their_header(ai_people: People) -> None:
    made = await make_connector(
        ai_people.admin, name="GitLab", auth_kind="header", header_name="PRIVATE-TOKEN"
    )
    assert made["auth_kind"] == "header" and made["header_name"] == "PRIVATE-TOKEN"
    bad: list[dict[str, Any]] = [
        {"auth_kind": "header"},  # no header name
        {"auth_kind": "bearer", "header_name": "X-Key"},  # bearer has its own
        {"auth_kind": "header", "header_name": "Host"},
        {"auth_kind": "header", "header_name": "Mcp-Session-Id"},
        {"auth_kind": "header", "header_name": "bad header"},
        {"auth_kind": "oauth"},
        {"auth_kind": "bearer", "secret": None},
    ]
    for fields in bad:
        body = {"name": "X", "secret": {"value": "v"}, **fields}
        response = await ai_people.admin.post(SHARED, json=body)
        assert response.status_code == 422, (fields, response.text)


async def test_shared_connectors_may_name_an_env_variable_personal_ones_may_not(
    ai_people: People,
) -> None:
    made = await make_connector(ai_people.admin, secret={"env": "HERD_AI_GITHUB_TOKEN"})
    assert made["secret_kind"] == "env"
    response = await ai_people.alice.post(
        PERSONAL,
        json={"name": "X", "auth_kind": "bearer", "secret": {"env": "HERD_AI_GITHUB_TOKEN"}},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "connector.env_not_allowed"


async def test_a_personal_connector_is_its_owners_alone(ai_people: People) -> None:
    mine = await make_connector(ai_people.alice, PERSONAL, name="Mein GitHub")
    path = f"{PERSONAL}/{mine['id']}"
    assert [c["id"] for c in (await ai_people.alice.get(PERSONAL)).json()["items"]] == [mine["id"]]
    assert (await ai_people.bob.get(PERSONAL)).json()["items"] == []
    assert (await ai_people.admin.get(SHARED)).json()["items"] == []
    for client in (ai_people.bob, ai_people.admin):
        for method, url, body in (
            ("GET", path, None),
            ("PATCH", path, {"name": "Y", "version": 1}),
            ("DELETE", f"{path}?version=1", None),
        ):
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (method, url, response.text)
            assert response.json()["error"]["code"] == "connector.not_found"
    as_shared = await ai_people.admin.get(f"{SHARED}/{mine['id']}")
    assert as_shared.json()["error"]["code"] == "connector.not_found"
    shared = await make_connector(ai_people.admin)
    response = await ai_people.alice.get(f"{PERSONAL}/{shared['id']}")
    assert response.json()["error"]["code"] == "connector.not_found"


async def test_without_ai_nobody_has_personal_connectors(people: People, secret_key: None) -> None:
    for client in (people.alice, people.gast):
        for method, url, body in (
            ("GET", PERSONAL, None),
            ("POST", PERSONAL, {"name": "X", "auth_kind": "bearer", "secret": {"value": "v"}}),
        ):
            response = await client.request(method, url, json=body)
            assert response.status_code == 404, (method, url, response.text)
            assert response.json()["error"]["code"] == "ai.not_found"


async def test_updates_name_the_version_and_audit_no_values(
    ai_people: People, session: AsyncSession
) -> None:
    made = await make_connector(ai_people.admin, auth_kind="header", header_name="X-Key")
    path = f"{SHARED}/{made['id']}"
    renamed = await ai_people.admin.patch(
        path, json={"name": "Neu", "header_name": "X-Api-Key", "version": 1}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "Neu" and renamed.json()["version"] == 2
    stale = await ai_people.admin.patch(path, json={"name": "Alt", "version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "connector.version_conflict"
    replaced = await ai_people.admin.patch(path, json={"secret": {"value": KEY}, "version": 2})
    assert replaced.status_code == 200 and replaced.json()["version"] == 3
    cleared = await ai_people.admin.patch(
        path, json={"auth_kind": "bearer", "header_name": None, "version": 3}
    )
    assert cleared.status_code == 200 and cleared.json()["header_name"] is None
    missing = await ai_people.admin.patch(path, json={"auth_kind": "header", "version": 4})
    assert missing.status_code == 422
    entries = (
        await session.scalars(
            select(AuditLog).where(AuditLog.action == "connector.updated").order_by(AuditLog.id)
        )
    ).all()
    assert [e.details for e in entries] == [
        {"fields": ["header_name", "name"]},
        {"fields": ["secret"], "secret": "enc"},
        {"fields": ["auth_kind", "header_name"]},
    ]


async def test_names_are_unique_per_owner(ai_people: People) -> None:
    await make_connector(ai_people.admin, name="GitHub")
    taken = await ai_people.admin.post(
        SHARED, json={"name": "github", "auth_kind": "bearer", "secret": {"value": "v"}}
    )
    assert taken.status_code == 409
    assert taken.json()["error"]["code"] == "connector.name_taken"
    await make_connector(ai_people.alice, PERSONAL, name="GitHub")  # her own
    await make_connector(ai_people.bob, PERSONAL, name="GitHub")  # and his


async def test_delete_names_the_version(ai_people: People, session: AsyncSession) -> None:
    made = await make_connector(ai_people.alice, PERSONAL)
    path = f"{PERSONAL}/{made['id']}"
    assert (await ai_people.alice.delete(f"{path}?version=2")).status_code == 409
    assert (await ai_people.alice.delete(f"{path}?version=1")).status_code == 204
    assert (await ai_people.alice.get(path)).status_code == 404
    deleted = await session.scalar(select(AuditLog).where(AuditLog.action == "connector.deleted"))
    assert deleted is not None and deleted.details == {"scope": "personal"}


async def test_lists_are_paginated(ai_people: People) -> None:
    for n in range(3):
        await make_connector(ai_people.admin, name=f"C{n}")
    first = (await ai_people.admin.get(f"{SHARED}?limit=2")).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = (await ai_people.admin.get(f"{SHARED}?limit=2&cursor={first['next_cursor']}")).json()
    assert [c["name"] for c in rest["items"]] == ["C2"] and rest["next_cursor"] is None


async def test_other_organisations_see_nothing(
    ai_people: People, session: AsyncSession, make_user: MakeUser
) -> None:
    made = await make_connector(ai_people.admin)
    other = Organization(name="Other")
    session.add(other)
    await session.flush()
    stranger = await make_user(SystemRole.OWNER, organization=other)
    actor = Actor(other.id, Principal.user(stranger.id), SystemRole.OWNER, frozenset())
    service = ConnectorService(session)
    assert (await service.list(actor, ConnectorScope.SHARED, PageParams())).items == []
    with pytest.raises(NotFound) as caught:
        await service.get(actor, ConnectorScope.SHARED, made["id"])
    assert caught.value.code == "connector.not_found"

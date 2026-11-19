"""What the database holds about purposes beyond the connector's own rows (fix wave of
the review of M10 task 13a): an MCP server names only `mcp` connectors and apps
(R13a-8), and going below the migration removes the calendar's rows first instead of
turning them into MCP ones (R13a-10). Migrations run inside a rolled-back transaction."""

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.core.migrations import alembic_config
from app.modules.mcp_servers.models import McpServer
from tests.factories_dms import People
from tests.factories_mcp import make_server
from tests.factories_oauth import make_oauth_client
from tests.factories_purposes import calendar_client, calendar_connector, sync_on
from tests.support.mcp_stub import McpStub
from tests.support.oauth_stub import OAuthStub

REVISION = "d5f8a1c3e7b9"  # m10 connector purpose
BEFORE = "b1c4e7a90d23"
NOW = datetime(2026, 11, 19, 8, 0, tzinfo=UTC)


async def test_an_mcp_server_never_names_a_calendar_connector_or_app(
    oauth_ready: OAuthStub, mcp_stub: McpStub, ai_people: People, session: AsyncSession
) -> None:
    """R13a-8: behind the service's back, the database refuses each (one at a time)."""
    await sync_on(ai_people.admin)
    admin = ai_people.users["admin"]
    google_app = await calendar_client(session, admin, oauth_ready)
    calendar = await calendar_connector(session, admin)
    shared = await make_server(ai_people.admin, mcp_stub)
    mcp_app = await make_oauth_client(ai_people.admin, oauth_ready, name="Stub-App")
    server_id = uuid.UUID(shared["id"])
    changes: list[tuple[dict[str, Any], str]] = [
        ({"connector_scope": "shared", "connector_id": calendar.id}, "fk_mcp_server_connector"),
        (
            {"connector_scope": "personal", "connector_id": None, "oauth_client_id": google_app.id},
            "fk_mcp_server_oauth_client",
        ),
        ({"purpose": "calendar"}, "ck_mcp_server_purpose"),
    ]
    for fields, constraint in changes:
        async with session.begin_nested() as nested:
            row = await session.get(McpServer, server_id, populate_existing=True)
            assert row is not None
            for name, value in fields.items():
                setattr(row, name, value)
            with pytest.raises(IntegrityError) as broken:
                await session.flush()
            assert constraint in str(broken.value.orig), constraint
            await nested.rollback()
    # What M8 names is still fine: an MCP app for a personal server.
    row = await session.get(McpServer, server_id, populate_existing=True)
    assert row is not None and row.purpose == "mcp"
    row.connector_scope, row.connector_id = "personal", None
    row.oauth_client_id = uuid.UUID(mcp_app["id"])
    await session.flush()


def _insert(connection: Connection, table: str, **values: object) -> uuid.UUID:
    row = {"id": uuid.uuid4(), **values}
    if table in {"connector", "oauth_client"}:
        row |= {"created_at": NOW, "updated_at": NOW, "version": 1}
    names = ", ".join(row)
    connection.execute(
        text(f"INSERT INTO {table} ({names}) VALUES ({', '.join(':' + n for n in row)})"), row
    )
    return row["id"]  # type: ignore[return-value]


def _app(connection: Connection, org: uuid.UUID, name: str, purpose: str) -> uuid.UUID:
    return _insert(
        connection,
        "oauth_client",
        org_id=org,
        name=name,
        authorization_endpoint="https://as.example.com/authorize",
        token_endpoint="https://as.example.com/token",
        client_id="c",
        client_secret_ref="enc:secret",
        token_auth="client_secret_post",
        scopes="",
        purpose=purpose,
    )


def _connector(
    connection: Connection, org: uuid.UUID, owner: uuid.UUID, purpose: str, **fields: object
) -> uuid.UUID:
    return _insert(
        connection,
        "connector",
        org_id=org,
        owner_id=owner,
        scope="personal",
        name=f"{purpose}:{uuid.uuid4()}",
        purpose=purpose,
        **fields,
    )


def _down_and_up(connection: Connection) -> dict[str, object]:
    config = alembic_config()
    config.attributes["connection"] = connection
    org = _insert(connection, "organization", name="Alt")
    owner = _insert(
        connection,
        "app_user",
        org_id=org,
        email=f"{uuid.uuid4()}@example.com",
        name="Owner",
        system_role="member",
        is_active=True,
        locale="de",
        version=1,
    )
    google = _app(connection, org, "Google", "calendar")
    mcp_app = _app(connection, org, "GitHub", "mcp")
    oauth = dict(auth_kind="oauth", secret_ref="enc:access", refresh_token_ref="enc:refresh")
    gone = [
        _connector(connection, org, owner, "calendar", oauth_client_id=google, **oauth),
        _connector(
            connection,
            org,
            owner,
            "calendar",
            auth_kind="header",
            header_name="Authorization",
            secret_ref="enc:basic",
        ),
    ]
    kept = [
        _connector(connection, org, owner, "mcp", oauth_client_id=mcp_app, **oauth),
        _connector(connection, org, owner, "mcp", auth_kind="bearer", secret_ref="enc:tok"),
    ]
    command.downgrade(config, BEFORE)

    def ids(table: str) -> set[uuid.UUID]:
        found = connection.execute(text(f"SELECT id FROM {table} WHERE org_id = :o"), {"o": org})
        return set(found.scalars())

    def columns(table: str) -> set[str]:
        found = connection.execute(
            text("SELECT column_name FROM information_schema.columns WHERE table_name = :t"),
            {"t": table},
        )
        return set(found.scalars())

    below = {
        "connectors": ids("connector"),
        "apps": ids("oauth_client"),
        "columns": {
            t for t in ("connector", "oauth_client", "mcp_server") if "purpose" in columns(t)
        },
    }
    command.upgrade(config, "head")
    purposes = connection.execute(
        text("SELECT DISTINCT purpose FROM connector WHERE org_id = :o"), {"o": org}
    ).scalars()
    return below | {
        "gone": set(gone),
        "kept": set(kept),
        "mcp_app": mcp_app,
        "after": set(purposes),
    }


async def test_going_below_the_migration_removes_calendar_rows_first(engine: AsyncEngine) -> None:
    """R13a-10: below d5f8a1c3e7b9 every row would count as MCP: a calendar access would
    show under "my connections" with its secret, a calendar app become nameable by an
    MCP server. The downgrade deletes calendar connectors, then calendar apps."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            found = await connection.run_sync(_down_and_up)
        finally:
            await transaction.rollback()
    assert found["connectors"] == found["kept"]
    assert found["apps"] == {found["mcp_app"]}
    assert found["columns"] == set()
    assert found["after"] == {"mcp"}  # 1.0.0's rows meet every rule on the way up

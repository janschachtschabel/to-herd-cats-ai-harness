"""Database roles of their own in a scratch target database (`factories_restore.target`):
a login role that owns the database and its schema `public` and is no superuser, as
the shipped stacks run the app (review M9b final, F2-1), and optionally a runtime role
for separate roles (J14). Both are dropped afterwards; without CREATEROLE the test is
skipped."""

import secrets
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import Settings
from app.core.db import make_engine
from tests.factories_restore import Target


@dataclass(frozen=True)
class Role:
    name: str
    password: str


@dataclass(frozen=True)
class Roles:
    owner: Role
    runtime: Role | None

    def owner_settings(self, target: Target) -> Settings:
        """The target as one role: the owner does everything."""
        url = target.settings.database().set(username=self.owner.name, password=self.owner.password)
        return target.settings.model_copy(
            update={"database_url": url.render_as_string(hide_password=False)}
        )

    def separate_settings(self, target: Target) -> Settings:
        """The target with separate roles: requests as the runtime role, migrations,
        backups and restores as the owner."""
        assert self.runtime is not None
        base = target.settings.database()
        runtime = base.set(username=self.runtime.name, password=self.runtime.password)
        return Settings(
            database_url=runtime.render_as_string(hide_password=False),
            migrate_database_url=base.set(username=self.owner.name, password=None).render_as_string(
                hide_password=False
            ),
            migrate_database_password=SecretStr(self.owner.password),
            database_runtime_role=self.runtime.name,
            data_dir=target.settings.data_dir,
            backup_dir=target.settings.backup_dir,
            secret_key=target.settings.secret_key,
        )


def _new_role() -> Role:
    return Role(f"herd_t_{uuid.uuid4().hex[:12]}", secrets.token_hex(16))


@asynccontextmanager
async def database_roles(target: Target, *, runtime: bool = False) -> AsyncIterator[Roles]:
    admin = make_engine(target.settings.database(), isolation_level="AUTOCOMMIT")
    roles = Roles(_new_role(), _new_role() if runtime else None)
    made = [r for r in (roles.owner, roles.runtime) if r is not None]
    try:
        async with admin.connect() as conn:
            allowed = await conn.scalar(
                text("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname = current_user")
            )
            if not allowed:
                pytest.skip("the test database's role cannot create roles (CREATEROLE)")
            for role in made:
                await conn.execute(
                    text(f"CREATE ROLE {role.name} LOGIN NOSUPERUSER PASSWORD '{role.password}'")
                )
            await conn.execute(text(f'ALTER DATABASE "{target.name}" OWNER TO {roles.owner.name}'))
            await conn.execute(text(f"ALTER SCHEMA public OWNER TO {roles.owner.name}"))
        yield roles
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f'ALTER DATABASE "{target.name}" OWNER TO current_user'))
            await conn.execute(
                text(
                    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity"
                    f" WHERE datname = '{target.name}' AND pid <> pg_backend_pid()"
                )
            )
            for role in made:
                exists = await conn.scalar(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :n"), {"n": role.name}
                )
                if exists:
                    await conn.execute(text(f"DROP OWNED BY {role.name}"))
                    await conn.execute(text(f"DROP ROLE {role.name}"))
        await admin.dispose()

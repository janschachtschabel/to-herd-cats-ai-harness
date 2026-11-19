"""Review M9b final, finding F2-8: a replace under separate database roles (J14) had no
test. After the swap the new schema `public` has no grants at all; the runtime role
gets them back only because the replace's migration grants them at its end
(`alembic/env.py`, `core/db_roles.grant_runtime_role`). Here, end to end: the owner
(no superuser) restores and replaces, and afterwards the runtime role reads and writes
data, may only read `alembic_version`, cannot restore, and sees maintenance off."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import make_engine
from app.core.db_roles import schema_owner_problem
from app.modules.maintenance.repository import MaintenanceRepository
from app.ops.replace import replace_running
from app.ops.restore import restore_into_empty
from tests.factories_restore import AT, Target, make_archive, source_settings
from tests.factories_roles import database_roles
from tests.real_db import RealDb
from tests.replace_helpers import NAME
from tests.support.clock import SettableClock


async def test_a_replace_under_separate_roles_gives_the_runtime_role_its_rights_back(
    real_db: RealDb,
    target: Target,
    tmp_path: Path,
    data_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = await make_archive(source_settings(tmp_path, data_dir))
    async with database_roles(target, runtime=True) as roles:
        assert roles.runtime is not None
        settings = roles.separate_settings(target)
        # The migration's grants read the process's settings (`alembic/env.py`).
        monkeypatch.setattr(get_settings(), "database_runtime_role", roles.runtime.name)
        await restore_into_empty(settings, archive, without_secrets=False, clock=SettableClock(AT))
        await replace_running(
            settings,
            archive,
            confirm=NAME,
            without_secrets=False,
            clock=SettableClock(AT),
            drain_seconds=0,
        )

        runtime = make_engine(settings.database())
        try:
            async with runtime.connect() as conn:
                assert await conn.scalar(text("SELECT current_user")) == roles.runtime.name
                assert await conn.scalar(text("SELECT count(*) FROM organization")) == 1
                hit = {"id": uuid.uuid4()}
                await conn.execute(
                    text("INSERT INTO rate_limit_hit (id, key, hit_at) VALUES (:id, 'f28', now())"),
                    hit,
                )
                await conn.execute(text("DELETE FROM rate_limit_hit WHERE id = :id"), hit)
                await conn.commit()
                assert await conn.scalar(text("SELECT version_num FROM alembic_version"))
                with pytest.raises(DBAPIError, match="permission denied"):
                    async with conn.begin_nested():
                        await conn.execute(text("UPDATE alembic_version SET version_num = 'x'"))
                await conn.rollback()
                assert await schema_owner_problem(conn) == "restore.not_schema_owner"
            async with AsyncSession(runtime) as session:
                assert (await MaintenanceRepository(session).current()).active is False
        finally:
            await runtime.dispose()

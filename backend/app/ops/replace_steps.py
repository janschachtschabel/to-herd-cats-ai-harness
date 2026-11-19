"""The swap step of a replace and what follows when it does not end well
(`replace.py` points 4; review M9b F1, F4, F5).

- `swap`: the archive's dump into the database (`swap.py`); an archive that changed
  after the checks fails with an `archive.*` code.
- `failed`: the swap rolled back (or never began): the old state is whole, so
  maintenance ends and `backup.restore_failed` is audited.
- `uncertain`: the database may hold neither state whole (`restore.swap_broken`,
  `restore.swap_unknown`): maintenance is turned on again and the attempt audited, both
  as far as the database still allows (the processes keep maintenance on while they
  cannot read it); nothing claims the old state.
"""

import logging
import tarfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core.clock import Clock
from app.core.config import Settings
from app.core.db import make_engine
from app.modules.audit.recorder import record_system
from app.modules.maintenance.repository import stay_on, stay_on_sql
from app.modules.maintenance.service import MaintenanceService
from app.ops.archive import DUMP_MEMBER, PREFIX, read_chunks
from app.ops.manifest import Manifest
from app.ops.pgtools import ToolFailed
from app.ops.restore import RestoreFailed
from app.ops.swap import SwapCommitted, SwapUncertain, swap_database

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Plan:
    settings: Settings
    archive: Path
    manifest: Manifest
    org_id: uuid.UUID
    clock: Clock
    via: str


async def swap(plan: Plan) -> None:
    """Like `restore._restore_database`: an archive that changed after the checks
    fails with an `archive.*` code, and the swap never commits half of a dump."""
    try:
        with tarfile.open(plan.archive, "r:") as tar:
            handle = tar.extractfile(PREFIX + DUMP_MEMBER)
            if handle is None:
                raise RestoreFailed("archive.member_missing")
            await swap_database(
                plan.settings, read_chunks(handle), tail_sql=stay_on_sql(plan.clock.now())
            )
    except (SwapCommitted, SwapUncertain):
        raise  # not a failure that left the old state: `_replace` tells them apart
    except ToolFailed as failed:
        raise RestoreFailed(failed.code) from None
    except KeyError:
        raise RestoreFailed("archive.member_missing") from None
    except (tarfile.TarError, EOFError):
        raise RestoreFailed("archive.truncated") from None
    except OSError:
        raise RestoreFailed("archive.unreadable") from None


async def uncertain(plan: Plan, code: str) -> None:
    """The swap ended and the database may hold neither state whole (review M9b F1):
    maintenance on again and the attempt audited, both as far as the database still
    allows (the processes keep maintenance on while they cannot read it)."""
    logger.warning("backup.restore_uncertain", extra={"code": code})
    engine = make_engine(plan.settings.migrate_database(), settings=plan.settings)
    try:
        async with engine.connect() as conn:
            await stay_on(conn, plan.clock.now())
            await conn.commit()
            async with AsyncSession(bind=conn) as session:
                details = {"archive": plan.archive.name, "code": code, "via": plan.via}
                await record_system(
                    session, plan.org_id, "backup.restore_failed", "organization", plan.org_id,
                    details,
                )  # fmt: skip
                await session.commit()
    except Exception as exc:
        logger.warning("backup.restore_uncertain_unrecorded", extra={"error": type(exc).__name__})
    finally:
        await engine.dispose()


async def failed(conn: AsyncConnection, plan: Plan, code: str) -> None:
    """The old state, whole: maintenance off and the attempt audited."""
    await conn.rollback()
    async with AsyncSession(bind=conn) as session:
        await MaintenanceService(session).end(plan.org_id, via=plan.via)
        details = {"archive": plan.archive.name, "code": code, "via": plan.via}
        await record_system(
            session, plan.org_id, "backup.restore_failed", "organization", plan.org_id, details
        )
        await session.commit()

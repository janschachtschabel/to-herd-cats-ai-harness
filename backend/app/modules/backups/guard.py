"""Who may see and handle backups (plan M9 decision 10): `backup.manage`, which only
an owner holds. Everyone else, administrators included, learns nothing about them: the
guard answers exactly like an unknown backup (404 `backup.not_found`)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, Actor, can
from app.core.errors import NotFound


async def require_backup_manage(session: AsyncSession, actor: Actor) -> None:
    if not await can(session, actor, Action.BACKUP_MANAGE):
        raise NotFound(code="backup.not_found")

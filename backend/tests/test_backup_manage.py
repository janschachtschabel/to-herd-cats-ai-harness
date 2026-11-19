"""`backup.manage` (plan M9 decision 10): only an owner holds it. An archive holds
direct messages that administrators read only through the audited inspection, so an
administrator is told nothing about backups: the guard answers exactly like an
unknown backup (404 `backup.not_found`)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import Action, can
from app.core.errors import NotFound
from app.core.permissions import SYSTEM_ROLE_ACTIONS
from app.core.principal import SystemRole
from app.modules.backups.guard import require_backup_manage
from tests.factories import MakeUser, login
from tests.test_access import actor_of


async def test_backup_manage_is_owner_only(
    session: AsyncSession, make_user: MakeUser, make_client
) -> None:  # type: ignore[no-untyped-def]
    assert {r for r, acts in SYSTEM_ROLE_ACTIONS.items() if Action.BACKUP_MANAGE in acts} == {
        SystemRole.OWNER
    }
    owner = await make_user(SystemRole.OWNER)
    await require_backup_manage(session, await actor_of(session, owner))
    unknown = NotFound(code="backup.not_found")
    for role in (SystemRole.ADMIN, SystemRole.MEMBER, SystemRole.GUEST):
        actor = await actor_of(session, await make_user(role))
        assert not await can(session, actor, Action.BACKUP_MANAGE)
        with pytest.raises(NotFound) as refused:
            await require_backup_manage(session, actor)
        assert (refused.value.status_code, refused.value.code) == (404, unknown.code)
        assert refused.value.message == unknown.message


async def test_only_the_owner_is_shown_backup_manage(make_user: MakeUser, make_client) -> None:  # type: ignore[no-untyped-def]
    shown = {}
    for role in (SystemRole.OWNER, SystemRole.ADMIN):
        user = await make_user(role)
        client: AsyncClient = await make_client(csrf=True)
        me = await login(client, user.email)
        shown[role] = "backup.manage" in me["permissions"]
    assert shown == {SystemRole.OWNER: True, SystemRole.ADMIN: False}

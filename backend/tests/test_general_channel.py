"""`#allgemein`: new installations get it at bootstrap, existing ones through the
migration's data step."""

import importlib.util
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.modules.messaging.models import Conversation
from app.modules.orgs.models import Organization
from app.modules.orgs.service import ensure_bootstrap
from app.modules.spaces.models import Space, SpaceKind


async def test_bootstrap_creates_the_general_channel(session: AsyncSession) -> None:
    boot = Settings(
        bootstrap_admin_email="boss@example.com", bootstrap_admin_password="pw-123456789"
    )
    await ensure_bootstrap(session, boot)
    general = (await session.scalars(select(Space).where(Space.kind == SpaceKind.OPEN))).one()
    channel = (await session.scalars(select(Conversation))).one()
    assert (channel.kind, channel.name, channel.space_id) == ("channel", "allgemein", general.id)
    assert channel.created_by_id is None  # set up by the system


def _conversations_migration():  # type: ignore[no-untyped-def]
    versions = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    (path,) = versions.glob("*_m3_conversations.py")
    spec = importlib.util.spec_from_file_location("m3_conversations", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


async def test_existing_installations_get_the_general_channel(
    session: AsyncSession, org: Organization, make_space
) -> None:
    """The migration's data step: the open space „Allgemein“ of every organisation
    that has one gets `#allgemein` (once, also when it runs again)."""
    general = await make_space(SpaceKind.OPEN, "Allgemein")
    await make_space(SpaceKind.OPEN, "Handbuch")
    connection = await session.connection()
    add = _conversations_migration().add_general_channels
    await connection.run_sync(add)
    await connection.run_sync(add)
    rows = (await session.scalars(select(Conversation))).all()
    assert [(c.name, c.space_id, c.org_id) for c in rows] == [("allgemein", general.id, org.id)]

"""Installation bootstrap: the organisation and its first owner."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.principal import SystemRole
from app.core.repository import advisory_xact_lock
from app.core.security import hash_password
from app.core.slug import slugify
from app.modules.orgs.models import Organization
from app.modules.orgs.repository import OrganizationRepository
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


async def ensure_bootstrap(session: AsyncSession, settings: Settings) -> None:
    """Create the organisation, an owner from HERD_BOOTSTRAP_*, the owner's personal
    space and the open space „Allgemein“, while nobody exists.

    Idempotent and safe when several replicas start at once: they queue on an advisory
    lock, and every one after the first finds a person and does nothing. The caller
    commits.
    """
    await advisory_xact_lock(session, "bootstrap")
    users = UserRepository(session)
    if await users.exists_any():
        return
    email, password = settings.bootstrap_admin_email, settings.bootstrap_admin_password
    if not (email and password):
        # Nobody can log in yet; the operator has to set the variables and restart.
        logger.warning("bootstrap.skipped", extra={"reason": "credentials_not_configured"})
        return
    orgs = OrganizationRepository(session)
    org = await orgs.get_default()
    if org is None:
        name = settings.bootstrap_org_name
        org = await orgs.add(Organization(name=name, slug=slugify(name)))
    owner = await users.add(
        User(
            org_id=org.id,
            email=email.lower(),
            name=email.split("@")[0],
            system_role=SystemRole.OWNER,
            password_hash=hash_password(password),
        )
    )
    spaces = SpaceService(session)
    await spaces.create_personal(owner)
    await spaces.create_general(org.id)
    logger.info("bootstrap.created", extra={"org_id": str(org.id), "user_id": str(owner.id)})

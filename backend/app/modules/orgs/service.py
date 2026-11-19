"""Installation bootstrap: the organisation and its first owner.

The owner's password passes the checks every password passes (`core/password_check.py`,
module review M9a, N6): a breached one or one holding a context word (product,
organisation, the address) refuses the bootstrap (`BootstrapRefused`, nothing created)
and the start fails (`launch.bootstrap`)."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ValidationFailed
from app.core.password_check import context_words, refuse_guessable
from app.core.principal import SystemRole
from app.core.repository import advisory_xact_lock
from app.core.security import hash_password_async
from app.modules.messaging.channels import ChannelService
from app.modules.orgs.models import Organization
from app.modules.orgs.repository import OrganizationRepository
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

logger = logging.getLogger(__name__)


class BootstrapRefused(Exception):  # noqa: N818 (a verdict)
    """HERD_BOOTSTRAP_ADMIN_PASSWORD is easy to guess; `code` says why (never the
    password)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def ensure_bootstrap(session: AsyncSession, settings: Settings) -> None:
    """Create the organisation, an owner from HERD_BOOTSTRAP_*, the owner's personal
    space and the open space „Allgemein“ with its channel `#allgemein`, while nobody
    exists.

    Idempotent and safe when several replicas start at once: they queue on an advisory
    lock, and every one after the first finds a person and does nothing. The caller
    commits.
    """
    await advisory_xact_lock(session, "bootstrap")
    users = UserRepository(session)
    if await users.exists_any():
        return
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password.get_secret_value()
    if not (email and password):
        # Nobody can log in yet; the operator has to set the variables and restart.
        logger.warning("bootstrap.skipped", extra={"reason": "credentials_not_configured"})
        return
    orgs = OrganizationRepository(session)
    org = await orgs.get_default()
    name = email.split("@")[0]
    org_name = org.name if org is not None else settings.bootstrap_org_name
    try:
        await refuse_guessable(password, context_words(org_name=org_name, email=email, name=name))
    except ValidationFailed as refused:
        logger.error("bootstrap.refused", extra={"reason": refused.code})
        raise BootstrapRefused(refused.code) from None
    if org is None:
        org = await orgs.add(Organization(name=org_name))
    owner = await users.add(
        User(
            org_id=org.id,
            email=email.lower(),
            name=name,
            system_role=SystemRole.OWNER,
            password_hash=await hash_password_async(password),
        )
    )
    spaces = SpaceService(session)
    await spaces.create_personal(owner)
    if (general := await spaces.create_general(org.id)) is not None:
        await ChannelService(session).create_general(org.id, general.id)
    logger.info("bootstrap.created", extra={"org_id": str(org.id), "user_id": str(owner.id)})

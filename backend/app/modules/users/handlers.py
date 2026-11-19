"""The outbox handler of self-registration (plan M9 task 5b), registered by name; the
worker imports this module (`app/worker/handlers.py`).

`notify_on_signup`, for `user.signup_pending`: a `signup` notification, bound to the
waiting account, for every active person whose system role grants `user.manage`
(read from the permission catalogue, not from a role name), while the account still
waits when the handler runs (decided before: nobody is told). Idempotent: a person
gets one notification per account and reason. Payloads carry ids only (no address,
no name); the activity view shows the name to those who see the entry.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox import Event
from app.core.permissions import SYSTEM_ROLE_ACTIONS, Action
from app.modules.messaging.notification_models import NotificationReason
from app.modules.messaging.notification_repository import NotificationRepository
from app.modules.messaging.notifications import announce
from app.modules.users.events import USER_SIGNUP_PENDING
from app.modules.users.repository import UserRepository
from app.worker.registry import handler

MANAGING_ROLES = tuple(r for r, acts in SYSTEM_ROLE_ACTIONS.items() if Action.USER_MANAGE in acts)


async def notify_on_signup(session: AsyncSession, event: Event) -> None:
    if event.type != USER_SIGNUP_PENDING or event.subject_type != "user":
        return
    users = UserRepository(session)
    account = await users.get_current(event.org_id, event.subject_id)
    if account is None or account.awaiting_approval_since is None:
        return
    managers: list[uuid.UUID] = await users.active_ids_with_roles(event.org_id, MANAGING_ROLES)
    rows = [(u, NotificationReason.SIGNUP) for u in managers if u != account.id]
    repo = NotificationRepository(session, event.org_id)
    for notification in await repo.add_for_account(account.id, rows):
        await announce(session, event, notification)


handler((USER_SIGNUP_PENDING,), "notify_on_signup")(notify_on_signup)

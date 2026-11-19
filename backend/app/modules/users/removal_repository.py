"""Deleting an account that never was active (a rejected self-registration, plan M9
task 5b and module review M9a, N4): the SQL of it. People who were ever active are
deactivated, never deleted (their authorship stays).

Such an account has nothing of its own beyond what signing up created and what an
administrator may have given it while it waited: its personal space (with its own
membership), its memberships in other spaces and in groups, and the notifications
addressed to it. The rest goes with the row (`ON DELETE CASCADE`): its identities,
sessions, own AI assignment and budgets, tokens, connectors, and the managers'
notifications about it (`notification.account_id`).
"""

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import PrincipalType
from app.modules.groups.models import GroupMember
from app.modules.messaging.notification_models import Notification
from app.modules.spaces.models import Space, SpaceMember
from app.modules.users.models import User


class AccountRemoval:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def delete_never_active(self, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        for membership in (SpaceMember, GroupMember):
            await self.session.execute(
                delete(membership).where(
                    membership.member_type == PrincipalType.USER, membership.member_id == user_id
                )
            )
        await self.session.execute(
            delete(Notification).where(
                Notification.org_id == org_id, Notification.user_id == user_id
            )
        )
        await self.session.execute(
            delete(Space).where(Space.org_id == org_id, Space.owner_user_id == user_id)
        )
        await self.session.execute(delete(User).where(User.org_id == org_id, User.id == user_id))

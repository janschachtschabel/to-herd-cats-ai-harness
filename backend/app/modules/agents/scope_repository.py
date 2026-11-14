"""The SQL of a run's audience (`scope.py`): what its conversation is, who takes part
in a direct message, which spaces all of them read, the open spaces, and whether a
space has guests among its members. Scoped by the organisation."""

import uuid

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.access_repository import person_reads_space
from app.core.principal import PrincipalType, SystemRole
from app.modules.groups.models import GroupMember
from app.modules.messaging.models import Conversation, ConversationKind, ConversationParticipant
from app.modules.spaces.models import Space, SpaceKind, SpaceMember
from app.modules.users.models import User


class ScopeRepository:
    def __init__(self, session: AsyncSession, org_id: uuid.UUID) -> None:
        self.session = session
        self.org_id = org_id

    async def conversation(
        self, conversation_id: uuid.UUID
    ) -> tuple[ConversationKind, uuid.UUID | None] | None:
        """The conversation's kind and space (None for a DM), if it exists."""
        stmt = select(Conversation.kind, Conversation.space_id).where(
            Conversation.org_id == self.org_id, Conversation.id == conversation_id
        )
        row = (await self.session.execute(stmt)).one_or_none()
        return (ConversationKind(row[0]), row[1]) if row is not None else None

    async def people(self, conversation_id: uuid.UUID) -> frozenset[uuid.UUID]:
        """The active people taking part in a direct message."""
        stmt = (
            select(User.id)
            .join(
                ConversationParticipant,
                and_(
                    ConversationParticipant.principal_type == PrincipalType.USER,
                    ConversationParticipant.principal_id == User.id,
                ),
            )
            .where(
                ConversationParticipant.org_id == self.org_id,
                ConversationParticipant.conversation_id == conversation_id,
                User.org_id == self.org_id,
                User.is_active.is_(True),
            )
        )
        return frozenset(await self.session.scalars(stmt))

    async def read_by_all(
        self, space_ids: set[uuid.UUID], people: frozenset[uuid.UUID]
    ) -> set[uuid.UUID]:
        """Which of the spaces every one of the people may read now (none: none)."""
        if not space_ids or not people:
            return set()
        place = aliased(Space)
        someone_not = exists(
            select(User.id).where(
                User.org_id == self.org_id,
                User.id.in_(sorted(people)),
                ~person_reads_space(place.id),
            )
        )
        stmt = select(place.id).where(
            place.org_id == self.org_id, place.id.in_(sorted(space_ids)), ~someone_not
        )
        return set(await self.session.scalars(stmt))

    async def open_ids(self) -> set[uuid.UUID]:
        stmt = select(Space.id).where(Space.org_id == self.org_id, Space.kind == SpaceKind.OPEN)
        return set(await self.session.scalars(stmt))

    async def has_guests(self, space_id: uuid.UUID) -> bool:
        """Whether a guest is a member of the space, directly or through a group."""
        guest = select(User.id).where(
            User.org_id == self.org_id, User.system_role == SystemRole.GUEST
        )
        in_group = select(GroupMember.group_id).where(
            GroupMember.member_type == PrincipalType.USER, GroupMember.member_id.in_(guest)
        )
        stmt = select(
            exists().where(
                SpaceMember.space_id == space_id,
                or_(
                    and_(
                        SpaceMember.member_type == PrincipalType.USER,
                        SpaceMember.member_id.in_(guest),
                    ),
                    and_(
                        SpaceMember.member_type == PrincipalType.GROUP,
                        SpaceMember.member_id.in_(in_group),
                    ),
                ),
            )
        )
        return bool(await self.session.scalar(stmt))

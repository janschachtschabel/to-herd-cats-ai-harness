"""Who may see a conversation, asked in two ways that must agree: per actor
(`visible_conversations`, for lists and checks) and for many people at once
(`readers_of`, for mentions, notifications and live delivery). A matrix of people
and conversations (channels, DMs and page threads: published, draft, in the trash)
holds them to the same answers."""

import itertools

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.permissions import SpaceRole
from app.core.principal import Principal, SystemRole
from app.modules.groups.repository import GroupRepository
from app.modules.messaging.channels import ChannelService
from app.modules.messaging.dms import DmService
from app.modules.messaging.models import Conversation
from app.modules.messaging.repository import readers_of
from app.modules.messaging.threads import ThreadService
from app.modules.messaging.visibility import ConversationReader
from app.modules.orgs.models import Organization
from app.modules.spaces.models import SpaceKind
from app.modules.users.models import User
from app.modules.wiki.service import PageService


async def _actor(session: AsyncSession, user: User) -> Actor:
    groups = await GroupRepository(session).group_ids_for(Principal.user(user.id))
    return Actor(user.org_id, Principal.user(user.id), SystemRole(user.system_role), groups)


async def test_both_ways_of_asking_agree(
    session: AsyncSession, make_user, make_space, make_group, owner_user: User
) -> None:
    people = {
        "owner": owner_user,
        "admin": await make_user(SystemRole.ADMIN),
        "member": await make_user(),
        "direct": await make_user(),
        "grouped": await make_user(),
        "guest": await make_user(SystemRole.GUEST),
        "guest_in": await make_user(SystemRole.GUEST),
        "inactive": await make_user(),
    }
    elsewhere = Organization(name="Andere")
    session.add(elsewhere)
    await session.flush()
    people["stranger"] = await make_user(organization=elsewhere)
    team_group = await make_group(members=[people["grouped"]])
    team = await make_space(
        SpaceKind.TEAM,
        members=[
            (people["direct"], SpaceRole.VIEWER),
            (team_group, SpaceRole.EDITOR),
            (people["guest_in"], SpaceRole.VIEWER),
            (people["inactive"], SpaceRole.ADMIN),
        ],
    )
    open_ = await make_space(SpaceKind.OPEN, members=[(people["guest_in"], SpaceRole.VIEWER)])
    owner = await _actor(session, owner_user)
    channels = ChannelService(session)
    conversations: list[Conversation] = [
        await channels.create(owner, team.id, "team", None),
        await channels.create(owner, open_.id, "offen", None),
    ]
    member = await _actor(session, people["member"])
    for others in (["guest"], ["inactive", "direct"], ["admin"]):
        ids = [people[name].id for name in others]
        conversations.append((await DmService(session).open(member, ids)).conversation)
    pages, threads = PageService(session), ThreadService(session)
    published = await pages.create(owner, team.id, None, "Veroeffentlicht", publish=True)
    draft = await pages.create(owner, team.id, None, "Entwurf")
    trashed = await pages.create(owner, team.id, None, "Weg", publish=True)
    open_page = await pages.create(owner, open_.id, None, "Offen", publish=True)
    for page in (published, draft, trashed, open_page):
        conversations.append(await threads.for_page(owner, page.id))
    await pages.trash(owner, trashed.id, trashed.version)
    people["inactive"].is_active = False
    await session.flush()

    everyone = [user.id for user in people.values()]
    reader = ConversationReader(session)
    for conversation, (name, user) in itertools.product(conversations, people.items()):
        actor = await _actor(session, user)
        per_actor = await reader.repo(actor).visible(conversation.id) is not None
        at_once = user.id in await readers_of(session, owner.org_id, conversation.id, everyone)
        assert per_actor == at_once, (conversation.kind, conversation.name, name)

    seen = {
        c.name or "dm": await readers_of(session, owner.org_id, c.id, everyone)
        for c in conversations[:2]
    }
    threads_seen = [
        await readers_of(session, owner.org_id, c.id, everyone) for c in conversations[5:]
    ]
    names = {user.id: name for name, user in people.items()}
    assert sorted(names[u] for u in seen["team"]) == [
        "admin",
        "direct",
        "grouped",
        "guest_in",
        "owner",
    ]
    assert sorted(names[u] for u in seen["offen"]) == [
        "admin",
        "direct",
        "grouped",
        "guest_in",
        "member",
        "owner",
    ]
    seen_threads = [sorted(names[u] for u in readers) for readers in threads_seen]
    assert seen_threads == [
        ["admin", "direct", "grouped", "guest_in", "owner"],  # published: the space's readers
        ["admin", "grouped", "owner"],  # a draft: `page.edit` (the group is editor)
        [],  # in the trash: nobody
        ["admin", "direct", "grouped", "guest_in", "member", "owner"],  # open space
    ]

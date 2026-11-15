"""The guards that hide what someone may not see (`tests/route_table.py`): an AI route,
a space, page, conversation, message, ticket status, ticket or sprint without a role
answers 404 exactly like something that does not exist; so does a page proposal, a
skill proposal one may not decide, a skill for people without AI, and one's access
tokens without `mcp.use`."""

from datetime import date

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.core.actor import Actor
from app.core.principal import Principal, SystemRole
from app.modules.messaging.channels import ChannelService
from app.modules.messaging.service import MessageService
from app.modules.proposals.service import ProposalService
from app.modules.skills.proposals import SkillProposalService
from app.modules.skills.service import SkillDraft, SkillService
from app.modules.spaces.models import Space
from app.modules.tickets.models import TicketStatus
from app.modules.tickets.service import TicketService
from app.modules.tickets.sprints import SprintService
from app.modules.users.models import User
from app.modules.wiki.service import PageService
from tests.route_table import BODIES, ROUTES, concrete


async def test_ai_routes_do_not_exist_for_people_without_the_right(
    member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    for client in (member_client, guest_client):
        for method, template, guard in ROUTES:
            if guard == "ai":
                body = BODIES.get((method, template), {})
                response = await client.request(method, concrete(template), json=body)
                assert response.status_code == 404, (method, template, response.text)
                assert response.json()["error"]["code"] == "ai.not_found"


async def test_agent_and_run_routes_do_not_exist_for_people_without_the_right(
    member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    codes = {
        "agent": "agent.not_found",
        "run": "run.not_found",
        "approval": "approval.not_found",
        "question": "question.not_found",
        "automation": "automation.not_found",
    }
    for client in (member_client, guest_client):
        for method, template, guard in ROUTES:
            if guard in codes:
                body = BODIES.get((method, template), {})
                response = await client.request(method, concrete(template), json=body)
                assert response.status_code == 404, (method, template, response.text)
                assert response.json()["error"]["code"] == codes[guard]


async def test_token_routes_do_not_exist_without_mcp_use(
    owner: AsyncClient, member_client: AsyncClient, guest_client: AsyncClient
) -> None:
    """The switch off: nobody's (admins neither); on: still not a guest's."""
    for switched_on in (False, True):
        if switched_on:
            body = {"enabled": True, "data_location": "external", "version": 1}
            assert (await owner.put("/api/ai/mcp", json=body)).status_code == 200
        clients = (guest_client,) if switched_on else (owner, member_client, guest_client)
        for client in clients:
            for method, template, guard in ROUTES:
                if guard == "token":
                    body = BODIES.get((method, template), {})
                    response = await client.request(method, concrete(template), json=body)
                    assert response.status_code == 404, (method, template, response.text)
                    assert response.json()["error"]["code"] == "token.not_found"


async def test_skill_routes_do_not_exist_for_people_without_ai(
    member_client: AsyncClient,
    guest_client: AsyncClient,
    session: AsyncSession,
    owner_user: User,
    open_space: Space,
) -> None:
    """Neither `ai.use` nor `skill.manage`: not even a skill of an open space, or an
    organisation-wide one, is there."""
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    service = SkillService(session)
    org_wide = await service.create(actor, SkillDraft("org", "d", "c"))
    in_open = await service.create(actor, SkillDraft("open", "d", "c", open_space.id))
    for skill_id in (org_wide.id, in_open.id):
        for client in (member_client, guest_client):
            for method, template, guard in ROUTES:
                if guard == "skill":
                    path = concrete(template, open_space.id, skill_id=skill_id)
                    body = BODIES.get((method, template), {})
                    response = await client.request(method, path, json=body)
                    assert response.status_code == 404, (method, template, response.text)
                    assert response.json()["error"]["code"] == "skill.not_found"


async def test_space_routes_hide_spaces_without_a_role(
    member_client: AsyncClient, team_space: Space
) -> None:
    for method, template, guard in ROUTES:
        if guard == "space":
            path = concrete(template, team_space.id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "space.not_found"


async def test_page_routes_hide_pages_without_a_role(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    page = await PageService(session).create(actor, team_space.id, None, "Geheim")
    for method, template, guard in ROUTES:
        if guard == "page":
            path = concrete(template, team_space.id, page.id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "page.not_found"


async def test_proposal_routes_hide_proposals_without_a_role(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    page = await PageService(session).create(actor, team_space.id, None, "Geheim", "alt")
    proposal = await ProposalService(session).propose_change(
        actor, page.id, "neu", "Grund", author=Principal.agent(uuid7())
    )
    for method, template, guard in ROUTES:
        if guard == "proposal":
            path = concrete(template, team_space.id, page.id, proposal_id=proposal.id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "proposal.not_found"


async def test_skill_proposal_routes_hide_proposals_from_who_may_not_decide(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    proposals = SkillProposalService(session)
    in_space = await proposals.propose_new(
        actor, team_space.id, "geheim", "d", "c", "r", author=Principal.agent(uuid7())
    )
    org_wide = await proposals.propose_new(
        actor, None, "fuer-alle", "d", "c", "r", author=Principal.agent(uuid7())
    )
    for proposal in (in_space, org_wide):
        for method, template, guard in ROUTES:
            if guard == "skill_proposal":
                path = concrete(template, team_space.id, proposal_id=proposal.id)
                body = BODIES.get((method, template))
                response = await member_client.request(method, path, json=body)
                assert response.status_code == 404, (method, template, response.text)
                assert response.json()["error"]["code"] == "skill_proposal.not_found"


async def test_conversation_routes_hide_conversations_without_a_role(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    channel = await ChannelService(session).create(actor, team_space.id, "geheim", None)
    message = (await MessageService(session).post(actor, channel.id, "Geheim")).message
    for method, template, guard in ROUTES:
        if guard in ("conversation", "message"):
            path = concrete(
                template, team_space.id, conversation_id=channel.id, message_id=message.id
            )
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == f"{guard}.not_found"


async def test_status_routes_hide_statuses_of_unseen_spaces(
    member_client: AsyncClient, team_space: Space, session: AsyncSession
) -> None:
    status_id = await session.scalar(
        select(TicketStatus.id).where(TicketStatus.space_id == team_space.id).limit(1)
    )
    for method, template, guard in ROUTES:
        if guard == "ticket_status":
            path = concrete(template, status_id=status_id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "ticket_status.not_found"


async def test_ticket_routes_hide_tickets_without_a_role(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    ticket = await TicketService(session).create(actor, team_space.id, title="Geheim")
    for method, template, guard in ROUTES:
        if guard == "ticket":
            path = concrete(template.replace("{number}", str(ticket.ticket.number)))
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "ticket.not_found"


async def test_sprint_routes_hide_sprints_of_unseen_spaces(
    member_client: AsyncClient, team_space: Space, session: AsyncSession, owner_user: User
) -> None:
    actor = Actor(owner_user.org_id, Principal.user(owner_user.id), SystemRole.OWNER, frozenset())
    sprint = await SprintService(session).create(
        actor,
        team_space.id,
        name="Geheim",
        goal="",
        starts_on=date(2026, 11, 16),
        ends_on=date(2026, 11, 27),
    )
    for method, template, guard in ROUTES:
        if guard == "sprint":
            path = concrete(template, sprint_id=sprint.id)
            body = BODIES.get((method, template))
            response = await member_client.request(method, path, json=body)
            assert response.status_code == 404, (method, template, response.text)
            assert response.json()["error"]["code"] == "sprint.not_found"

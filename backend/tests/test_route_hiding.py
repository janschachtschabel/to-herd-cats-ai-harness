"""The guards that hide what someone may not see (`tests/route_table.py`): an AI route,
a space, page, conversation, message, ticket status, ticket or sprint without a role
answers 404 exactly like something that does not exist; so does a page proposal."""

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
    codes = {"agent": "agent.not_found", "run": "run.not_found"}
    for client in (member_client, guest_client):
        for method, template, guard in ROUTES:
            if guard in codes:
                body = BODIES.get((method, template), {})
                response = await client.request(method, concrete(template), json=body)
                assert response.status_code == 404, (method, template, response.text)
                assert response.json()["error"]["code"] == codes[guard]


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

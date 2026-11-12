"""People and logged-in clients for tests.

Fixtures: `org`, `owner_user`, `member`, `guest` (users) and `owner`, `member_client`,
`guest_client` (logged-in httpx clients with the CSRF header), plus `make_user(...)`.
Every person made here has a personal space, like one made through the API.
"""

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.principal import SystemRole
from app.core.security import hash_password
from app.modules.orgs.models import Organization
from app.modules.spaces.service import SpaceService
from app.modules.users.models import User

CSRF = {"X-Requested-With": "herd"}
PASSWORD = "test-password-123"
# argon2 is slow on purpose; one hash serves every test user.
_PASSWORD_HASH = hash_password(PASSWORD)

MakeUser = Callable[..., Awaitable[User]]


async def login(client: AsyncClient, email: str, password: str = PASSWORD) -> dict[str, Any]:
    response = await client.post(
        "/api/auth/login", json={"email": email, "password": password}, headers=CSRF
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.fixture
async def org(session: AsyncSession) -> Organization:
    organization = Organization(name="Test Org", slug="test-org")
    session.add(organization)
    await session.flush()
    return organization


@pytest.fixture
async def make_user(session: AsyncSession, org: Organization) -> MakeUser:
    counter = 0

    async def _make(
        role: SystemRole | str = SystemRole.MEMBER,
        *,
        email: str | None = None,
        name: str | None = None,
        is_active: bool = True,
        organization: Organization | None = None,
    ) -> User:
        nonlocal counter
        counter += 1
        user = User(
            org_id=(organization or org).id,
            email=email or f"{role}{counter}@example.com",
            name=name or f"{str(role).title()} {counter}",
            password_hash=_PASSWORD_HASH,
            system_role=SystemRole(role),
            is_active=is_active,
        )
        session.add(user)
        await session.flush()
        await SpaceService(session).create_personal(user)  # as UserService.create does
        return user

    return _make


async def _logged_in(make_client: Callable[..., Awaitable[AsyncClient]], user: User) -> AsyncClient:
    client = await make_client(csrf=True)
    await login(client, user.email)
    return client


@pytest.fixture
async def owner_user(make_user: MakeUser) -> User:
    return await make_user(SystemRole.OWNER, email="owner@example.com", name="Olga Owner")


@pytest.fixture
async def member(make_user: MakeUser) -> User:
    return await make_user(SystemRole.MEMBER, email="member@example.com", name="Max Member")


@pytest.fixture
async def guest(make_user: MakeUser) -> User:
    return await make_user(SystemRole.GUEST, email="guest@example.com", name="Gina Guest")


@pytest.fixture
async def owner(
    make_client: Callable[..., Awaitable[AsyncClient]], owner_user: User
) -> AsyncClient:
    return await _logged_in(make_client, owner_user)


@pytest.fixture
async def member_client(
    make_client: Callable[..., Awaitable[AsyncClient]], member: User
) -> AsyncClient:
    return await _logged_in(make_client, member)


@pytest.fixture
async def guest_client(
    make_client: Callable[..., Awaitable[AsyncClient]], guest: User
) -> AsyncClient:
    return await _logged_in(make_client, guest)

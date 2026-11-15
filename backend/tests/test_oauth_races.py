"""Token renewal under real commits (`tests/real_db.py`): two workers that find the
same token expiring, or both got a 401 with it, renew on their own connections at
once; the connector's lock lets one of them call the provider, and the other takes
the token it stored. With a provider that rotates refresh tokens (GitHub, GitLab), a
second refresh with the old one would fail and disconnect the connector."""

import asyncio
from datetime import timedelta

from sqlalchemy import update

from app.core import secrets
from app.core.models_base import utcnow
from app.modules.connectors.models import Connector
from app.modules.oauth import tokens
from tests.factories import login
from tests.factories_connectors import SHARED
from tests.factories_oauth import connect, make_oauth_client
from tests.real_db import MakeRealClient, RealDb
from tests.support.oauth_stub import OAuthStub


async def test_two_workers_renew_once(
    real_db: RealDb,
    make_real_client: MakeRealClient,
    oauth_egress: OAuthStub,
    public_url: str,
    secret_key: None,
) -> None:
    owner = await make_real_client()
    await login(owner, real_db.owner_email)
    app = await make_oauth_client(owner, oauth_egress)
    body = {"name": "Stub", "auth_kind": "oauth", "oauth_client_id": app["id"]}
    connector = (await owner.post(SHARED, json=body)).json()
    assert (await connect(owner, SHARED, connector["id"], oauth_egress))["status"] == "connected"
    oauth_egress.state.delay = 0.3  # the first renewal is still at the provider
    for used in (oauth_egress.state.issued[-1], None):
        if used is None:
            async with real_db.database.session_factory() as session, session.begin():
                await session.execute(
                    update(Connector).values(token_expires_at=utcnow() + timedelta(seconds=5))
                )
        before = len(oauth_egress.state.token_requests("refresh_token"))
        both = await asyncio.gather(
            *(tokens.renew(real_db.org_id, connector["id"], used=used) for _ in range(2))
        )
        assert both[0] == both[1] == {"Authorization": f"Bearer {oauth_egress.state.issued[-1]}"}
        assert len(oauth_egress.state.token_requests("refresh_token")) == before + 1
    async with real_db.database.session_factory() as session:
        row = await session.get(Connector, connector["id"])
        assert row is not None and row.secret_ref is not None
        assert secrets.resolve(row.secret_ref).get_secret_value() == oauth_egress.state.issued[-1]

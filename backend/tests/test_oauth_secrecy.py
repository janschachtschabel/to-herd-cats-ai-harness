"""Nothing of an OAuth flow leaks (plan M8, global constraints): the authorization
code, the state, the PKCE verifier, the access and refresh tokens and the client
secret are in no log line, audit entry, outbox event, error body or trace span; the
redirect after the callback names a fixed status, never what the provider said."""

import json
from datetime import timedelta
from urllib.parse import parse_qsl, urlsplit

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.core.config import get_settings
from app.core.models_base import utcnow
from app.core.outbox import EventOutbox
from app.core.telemetry import _tracer_provider
from app.modules.audit.models import AuditLog
from app.modules.connectors.models import Connector
from app.modules.oauth import tokens
from app.modules.oauth.models import OAuthFlow
from tests.factories_connectors import SHARED
from tests.factories_dms import People
from tests.factories_oauth import CALLBACK, authorize, make_oauth_client, query_of
from tests.support.oauth_stub import OAuthStub

_SPANS = InMemorySpanExporter()
_tracer_provider(get_settings()).add_span_processor(SimpleSpanProcessor(_SPANS))


async def test_no_code_state_verifier_token_or_client_secret_anywhere(
    oauth_ready: OAuthStub,
    ai_people: People,
    session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _SPANS.clear()
    app = await make_oauth_client(ai_people.admin, oauth_ready)
    body = {"name": "Stub", "auth_kind": "oauth", "oauth_client_id": app["id"]}
    connector = (await ai_people.admin.post(SHARED, json=body)).json()
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    flow = await session.scalar(select(OAuthFlow))
    assert flow is not None and flow.verifier_ref.startswith("enc:")
    verifier = secrets.resolve(flow.verifier_ref).get_secret_value()
    query = oauth_ready.state.authorize(url)
    secret_words = [query["code"], query["state"], verifier]
    callback = await ai_people.admin.get(CALLBACK, params=query)
    location = callback.headers["location"]
    assert query_of(location)["status"] == "connected"
    first_access = oauth_ready.state.issued[-1]
    await session.execute(
        update(Connector).values(token_expires_at=utcnow() + timedelta(seconds=1))
    )
    connected = await session.get(Connector, connector["id"])
    assert connected is not None
    await tokens.bearer_headers(connected)
    second_access = oauth_ready.state.issued[-1]
    await ai_people.admin.post(f"{SHARED}/{connector['id']}/disconnect", json={"version": 2})
    oauth_ready.state.failures.append(400)
    url = await authorize(ai_people.admin, SHARED, connector["id"])
    failed = await ai_people.admin.get(CALLBACK, params=oauth_ready.state.authorize(url))
    assert query_of(failed.headers["location"])["status"] == "failed"
    secret_words += [
        first_access,
        second_access,
        f"rt-{first_access[3:]}",
        f"rt-{second_access[3:]}",
        str(oauth_ready.state.client_secret),
    ]
    places = {
        "logs": capsys.readouterr().out + capsys.readouterr().err,
        "audit": json.dumps([a.details for a in (await session.scalars(select(AuditLog))).all()]),
        "outbox": json.dumps(
            [e.payload for e in (await session.scalars(select(EventOutbox))).all()]
        ),
        "redirects": location + failed.headers["location"],
        "spans": json.dumps(
            [dict(s.attributes or {}) | {"name": s.name} for s in _SPANS.get_finished_spans()]
        ),
        "answers": (await ai_people.admin.get(SHARED)).text,
    }
    assert "oauth.token_request" in places["logs"]
    for where, text in places.items():
        for word in secret_words:
            assert word not in text, (where, word)
    assert set(dict(parse_qsl(urlsplit(location).query))) == {"status", "connector", "scope"}

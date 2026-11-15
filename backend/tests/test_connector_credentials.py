"""What a connector puts on an outbound request (plan M8 decision 9): its header with
the secret, formed only at the moment of the call; an unusable reference is a typed
failure that names nothing of the value."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import secrets
from app.modules.connectors.credentials import CredentialUnavailable, headers_for
from app.modules.connectors.models import AuthKind, Connector, ConnectorScope
from app.modules.orgs.models import Organization


def _connector(org: Organization, kind: AuthKind, ref: str, header: str | None) -> Connector:
    return Connector(
        org_id=org.id,
        scope=ConnectorScope.SHARED,
        name="C",
        auth_kind=kind,
        header_name=header,
        secret_ref=ref,
    )


async def test_bearer_and_header_connectors_form_their_header(
    org: Organization, session: AsyncSession, secret_key: None
) -> None:
    ref = secrets.encrypt("tok-123")
    bearer = _connector(org, AuthKind.BEARER, ref, None)
    assert headers_for(bearer) == {"Authorization": "Bearer tok-123"}
    header = _connector(org, AuthKind.HEADER, ref, "PRIVATE-TOKEN")
    assert headers_for(header) == {"PRIVATE-TOKEN": "tok-123"}


async def test_an_unusable_secret_is_a_typed_failure(
    org: Organization, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HERD_AI_UNSET_TOKEN", raising=False)
    connector = _connector(org, AuthKind.BEARER, "env:HERD_AI_UNSET_TOKEN", None)
    with pytest.raises(CredentialUnavailable) as caught:
        headers_for(connector)
    assert "HERD_AI_UNSET_TOKEN" not in str(caught.value)
    assert caught.value.__cause__ is None and caught.value.__suppress_context__

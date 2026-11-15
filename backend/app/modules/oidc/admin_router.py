"""OIDC administration (`user.manage`, anyone else: 403 like every `/api/admin` route):
providers and the accounts people have linked."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.oidc.identities import IdentityService
from app.modules.oidc.models import OidcProvider
from app.modules.oidc.schemas import (
    IdentityOut,
    ProviderCheckOut,
    ProviderCreate,
    ProviderOut,
    ProviderUpdate,
)
from app.modules.oidc.service import ProviderService, callback_url

providers = APIRouter(prefix="/admin/oidc-providers", tags=["oidc"])
user_identities = APIRouter(prefix="/admin/users", tags=["oidc"])


def _out(provider: OidcProvider) -> ProviderOut:
    return ProviderOut.of(provider, callback_url(provider))


@providers.get("", response_model=Page[ProviderOut])
async def list_providers(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[ProviderOut]:
    page = await ProviderService(session).list(actor, params)
    return Page[ProviderOut](items=[_out(p) for p in page.items], next_cursor=page.next_cursor)


@providers.post("", response_model=ProviderOut, status_code=201)
async def create_provider(
    body: ProviderCreate, actor: ActorDep, session: SessionDep
) -> ProviderOut:
    return _out(await ProviderService(session).create(actor, body))


@providers.get("/{provider_id}", response_model=ProviderOut)
async def get_provider(provider_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> ProviderOut:
    return _out(await ProviderService(session).get(actor, provider_id))


@providers.patch("/{provider_id}", response_model=ProviderOut)
async def update_provider(
    provider_id: uuid.UUID, body: ProviderUpdate, actor: ActorDep, session: SessionDep
) -> ProviderOut:
    return _out(await ProviderService(session).update(actor, provider_id, body))


@providers.delete("/{provider_id}", status_code=204)
async def delete_provider(
    provider_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    await ProviderService(session).delete(actor, provider_id, version)


@providers.post("/{provider_id}/check", response_model=ProviderCheckOut)
async def check_provider(
    provider_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> ProviderCheckOut:
    """Discovery and the JWKS, fetched now through the egress guard; a fixed code."""
    return await ProviderService(session).check(actor, provider_id)


@user_identities.get("/{user_id}/identities", response_model=Page[IdentityOut])
async def list_user_identities(
    user_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[IdentityOut]:
    page = await IdentityService(session).list(actor, user_id, params, as_admin=True)
    return Page[IdentityOut](
        items=[IdentityOut.of(i, p) for i, p in page.items], next_cursor=page.next_cursor
    )


@user_identities.delete("/{user_id}/identities/{identity_id}", status_code=204)
async def unlink_user_identity(
    user_id: uuid.UUID, identity_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> None:
    await IdentityService(session).unlink(actor, user_id, identity_id, as_admin=True)

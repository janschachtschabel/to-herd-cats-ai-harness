import uuid
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.wiki.present import page_out
from app.modules.wiki.schemas import ExpectedVersion, PageOut
from app.modules.wiki.version_schemas import DiffOut, VersionLabelIn, VersionOut, VersionSummaryOut
from app.modules.wiki.versions import VersionService

page_versions = APIRouter(prefix="/pages/{page_id}", tags=["wiki"])

Number = Annotated[int, Path(ge=1, le=2_147_483_647)]


@page_versions.get("/versions", response_model=Page[VersionSummaryOut])
async def list_versions(
    page_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[VersionSummaryOut]:
    page = await VersionService(session).list(actor, page_id, params)
    return Page[VersionSummaryOut](
        items=[VersionSummaryOut.of(row) for row in page.items], next_cursor=page.next_cursor
    )


@page_versions.get("/versions/{number}", response_model=VersionOut)
async def get_version(
    page_id: uuid.UUID, number: Number, actor: ActorDep, session: SessionDep
) -> VersionOut:
    return VersionOut.of(await VersionService(session).get(actor, page_id, number))


@page_versions.patch("/versions/{number}", response_model=VersionSummaryOut)
async def label_version(
    page_id: uuid.UUID, number: Number, body: VersionLabelIn, actor: ActorDep, session: SessionDep
) -> VersionSummaryOut:
    row = await VersionService(session).label(actor, page_id, number, body.label)
    return VersionSummaryOut.of(row)


@page_versions.post("/versions/{number}/restore", response_model=PageOut)
async def restore_version(
    page_id: uuid.UUID, number: Number, body: ExpectedVersion, actor: ActorDep, session: SessionDep
) -> PageOut:
    page = await VersionService(session).restore(actor, page_id, number, body.version)
    return await page_out(session, actor, page)


@page_versions.get("/diff", response_model=DiffOut)
async def diff_versions(
    page_id: uuid.UUID,
    from_number: Annotated[int, Query(alias="from", ge=1, le=2_147_483_647)],
    to_number: Annotated[int, Query(alias="to", ge=1, le=2_147_483_647)],
    actor: ActorDep,
    session: SessionDep,
) -> DiffOut:
    diff = await VersionService(session).diff(actor, page_id, from_number, to_number)
    return DiffOut.of(from_number, to_number, diff)

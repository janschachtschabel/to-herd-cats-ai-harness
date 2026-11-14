"""Automation routes (plan M7 task 7; `service.py`, `control.py`). One the caller may
not see answers 404 `automation.not_found`; lists and the preview for people without
`ai.use` (or `agent.manage`) 404 `ai.not_found`."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.pagination import Page, PageParams
from app.modules.auth.deps import ActorDep, SessionDep
from app.modules.automations.control import AutomationControl
from app.modules.automations.schemas import (
    AutomationCreate,
    AutomationOut,
    AutomationUpdate,
    FiringOut,
    PreviewIn,
    PreviewOut,
    VersionIn,
)
from app.modules.automations.service import AutomationService, AutomationView
from app.modules.automations.views import automation_out, firing_out

automations = APIRouter(prefix="/automations", tags=["automations"])
agent_automations = APIRouter(prefix="/agents", tags=["automations"])
space_automations = APIRouter(prefix="/spaces", tags=["automations"])


@automations.get("", response_model=Page[AutomationOut])
async def my_automations(
    params: Annotated[PageParams, Query()], actor: ActorDep, session: SessionDep
) -> Page[AutomationOut]:
    """The caller's own automations, newest first."""
    return _page(await AutomationService(session).mine(actor, params))


@agent_automations.get("/{agent_id}/automations", response_model=Page[AutomationOut])
async def automations_of_agent(
    agent_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[AutomationOut]:
    """Every automation of the agent (`agent.manage`)."""
    return _page(await AutomationService(session).of_agent(actor, agent_id, params))


@space_automations.get("/{space_id}/automations", response_model=Page[AutomationOut])
async def automations_of_space(
    space_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[AutomationOut]:
    """The automations at places in the space that the caller may see."""
    return _page(await AutomationService(session).of_space(actor, space_id, params))


@automations.post("", response_model=AutomationOut, status_code=201)
async def create_automation(
    body: AutomationCreate, actor: ActorDep, session: SessionDep
) -> AutomationOut:
    return automation_out(await AutomationService(session).create(actor, body))


@automations.post("/preview", response_model=PreviewOut)
async def preview_terms(body: PreviewIn, actor: ActorDep, session: SessionDep) -> PreviewOut:
    """The next five terms of a schedule, refused like a save would refuse it."""
    return PreviewOut(terms=await AutomationService(session).preview(actor, body.schedule))


@automations.get("/{automation_id}", response_model=AutomationOut)
async def get_automation(
    automation_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> AutomationOut:
    return automation_out(await AutomationService(session).get(actor, automation_id))


@automations.patch("/{automation_id}", response_model=AutomationOut)
async def update_automation(
    automation_id: uuid.UUID, body: AutomationUpdate, actor: ActorDep, session: SessionDep
) -> AutomationOut:
    """Its words or its schedule (its owner only; the kind stays)."""
    return automation_out(await AutomationService(session).update(actor, automation_id, body))


@automations.post("/{automation_id}/pause", response_model=AutomationOut)
async def pause_automation(
    automation_id: uuid.UUID, body: VersionIn, actor: ActorDep, session: SessionDep
) -> AutomationOut:
    view = await AutomationControl(session).pause(actor, automation_id, body.version)
    return automation_out(view)


@automations.post("/{automation_id}/resume", response_model=AutomationOut)
async def resume_automation(
    automation_id: uuid.UUID, body: VersionIn, actor: ActorDep, session: SessionDep
) -> AutomationOut:
    """Runs again (`paused_reason` cleared, failures counted anew)."""
    view = await AutomationControl(session).resume(actor, automation_id, body.version)
    return automation_out(view)


@automations.delete("/{automation_id}", status_code=204)
async def delete_automation(
    automation_id: uuid.UUID,
    version: Annotated[int, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> None:
    """Gone for the API and never due again; its runs stay as history."""
    await AutomationControl(session).delete(actor, automation_id, version)


@automations.get("/{automation_id}/firings", response_model=Page[FiringOut])
async def automation_log(
    automation_id: uuid.UUID,
    params: Annotated[PageParams, Query()],
    actor: ActorDep,
    session: SessionDep,
) -> Page[FiringOut]:
    """Its terms, newest first: how each went and the run it started."""
    page = await AutomationService(session).log(actor, automation_id, params)
    return Page[FiringOut](items=[firing_out(f) for f in page.items], next_cursor=page.next_cursor)


def _page(page: Page[AutomationView]) -> Page[AutomationOut]:
    return Page[AutomationOut](
        items=[automation_out(v) for v in page.items], next_cursor=page.next_cursor
    )

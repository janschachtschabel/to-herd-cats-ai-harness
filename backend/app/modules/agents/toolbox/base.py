"""What every tool of a run is and gets (plan M6 decisions 1 to 3).

A tool is a `ToolSpec`: its name and description for the model, the model of its
arguments (checked before it runs), and `run`, which does the work through the
services with the run's actor.

`run` gets a `ToolContext`. Its `session` is the transaction of the tool's step: the
host checked in it, first thing, that the run is still this take-up's (the run's row
locked), and writes the tool call's `run_event` in it after `run` returns. So a tool
that writes (through the services, with `ctx.actor`) commits its effect and its
journal entry together or not at all: a run taken up again finds the entry and does
not run the tool again, or finds none and finds no effect either. A tool never
commits, and never opens a transaction of its own.

`run` answers with a `ToolResult` (for the model; the loop frames and cuts it, the
event keeps all of it), or with `Wait` when the run must wait for a person (a
release, a question). The host then sets the run `waiting` in the same transaction,
records no result for the call, and the call is run again once the run is resumed.
What a tool read it notes in `ctx.reads` (the checks before every model call cover
it, and the event records it for a replay).
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.modules.agents.actor import Reads
from app.modules.ai.models import DataLocation
from app.runtime.loop import ToolResult

NOT_FOUND = "Nothing found (or not readable)."


@dataclass(frozen=True, slots=True)
class RunRef:
    """The run a tool works for (ids only)."""

    id: uuid.UUID
    org_id: uuid.UUID
    agent_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: AsyncSession
    actor: Actor
    location: DataLocation
    reads: Reads
    run: RunRef


@dataclass(frozen=True, slots=True)
class Wait:
    """The run waits for a person until `until` (then `waiting_timeout`)."""

    until: datetime


Runner = Callable[[ToolContext, Any], Awaitable[ToolResult | Wait]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    args: type[BaseModel]
    run: Runner

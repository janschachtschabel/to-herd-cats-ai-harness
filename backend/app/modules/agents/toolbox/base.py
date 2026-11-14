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

A tool an agent may use only with a person's release (`confirm`, plan M6 decision 4)
names what a call would change (`subjects`: each object with its version and space;
None for a call that changes nothing, such as `update_page`'s preview) and what a
person must be able to do there to release it (`action`); see `approvals/gate.py`.
"""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.permissions import Action
from app.modules.agents.actor import Reads
from app.modules.ai.models import DataLocation
from app.runtime.loop import ToolResult

NOT_FOUND = "Nothing found (or not readable)."


class Effect(StrEnum):
    """What a tool does: reads, proposes (a human decides), or writes."""

    READ = "read"
    PROPOSE = "propose"
    WRITE = "write"


class Grant(StrEnum):
    """How an agent may use a tool (spec 8.1), from loose to strict."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    BLOCK = "block"

    @property
    def strictness(self) -> int:
        return list(Grant).index(self)


@dataclass(frozen=True, slots=True)
class RunRef:
    """The run a tool works for (ids only)."""

    id: uuid.UUID
    org_id: uuid.UUID
    agent_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    reply_to: uuid.UUID | None = None  # the thread its messages go to (None: top level)
    chain_depth: int = 0  # handovers from agent to agent that led to the run


@dataclass(frozen=True, slots=True)
class CallRef:
    """The model's tool call a tool runs for: its step and the provider's call id
    (unique together within a run; stable when the run is taken up again)."""

    step: int
    id: str


@dataclass(frozen=True, slots=True)
class ToolContext:
    session: AsyncSession
    actor: Actor
    location: DataLocation
    reads: Reads
    run: RunRef
    call: CallRef | None = None  # None only outside a run (a tool called directly)


@dataclass(frozen=True, slots=True)
class Subject:
    """An object a call would change, as it is now: a release is bound to `version`
    (0 for what has none); `space_id` is where a person must be able to do it."""

    kind: str
    id: uuid.UUID
    version: int
    space_id: uuid.UUID | None


@dataclass(frozen=True, slots=True)
class Wait:
    """The run waits for a person until `until` (then `waiting_timeout`)."""

    until: datetime


Runner = Callable[[ToolContext, Any], Awaitable[ToolResult | Wait]]
Subjects = Callable[[ToolContext, Any], Awaitable[list[Subject] | None]]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """`level`: the lowest autonomy level (1 to 3) whose default allows the tool."""

    name: str
    description: str
    args: type[BaseModel]
    run: Runner
    level: int = 1
    effect: Effect = Effect.READ
    subjects: Subjects | None = None  # None: the call changes no object (release: args)
    action: Action | None = None  # what the releasing person must be able to do there

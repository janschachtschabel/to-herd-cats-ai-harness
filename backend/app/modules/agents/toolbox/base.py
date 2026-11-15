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
person must be able to do there to release it (`action`, or `action_of` where that
depends on the call: `assign_ticket` asks the ticket service's rule); see
`approvals/gate.py`.
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
from app.core.authorship import Authorship
from app.core.permissions import Action
from app.core.principal import Principal
from app.modules.agents.actor import Reads
from app.modules.agents.repository import AgentRepository
from app.modules.ai.models import DataLocation
from app.modules.wiki.models import VersionSource
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
class CallContext:
    """What a tool needs that does not belong to a run: the transaction, the actor
    whose rights it uses, the data location the AI policy treats the reader as, and
    what was read. A reading tool that takes only this can also serve a caller from
    outside a run (`/mcp`, plan M8 task 2); mypy keeps it from reaching for a run."""

    session: AsyncSession
    actor: Actor
    location: DataLocation
    reads: Reads

    @property
    def agent_self(self) -> uuid.UUID | None:
        """The agent a caller acts as, where "me" means an agent rather than the
        actor (an agent token at `/mcp`); a run's "me" is its asker."""
        return None


@dataclass(frozen=True, slots=True)
class WriteContext(CallContext):
    """What a writing tool needs besides: for whom it writes, how it keys what it
    writes, and where it may post. A run (`ToolContext`) writes for its agent, keyed by
    the run (a run taken up again writes nothing twice); a person's token at `/mcp`
    (`mcp_tools/context.py`) writes for the person with the token's name."""

    @property
    def by(self) -> Authorship:
        raise NotImplementedError

    @property
    def source(self) -> VersionSource:
        """The source of a page version the tool writes."""
        raise NotImplementedError

    def key(self, name: str, *parts: object) -> uuid.UUID:
        """A key for what a call writes (a message's `client_id`)."""
        raise NotImplementedError

    def binding(self) -> uuid.UUID:
        """What a preview's token is bound to (`update_page`): stable across the calls
        of one writer."""
        raise NotImplementedError

    def answers_in(self, conversation_id: uuid.UUID) -> bool:
        """Whether the conversation is the one the writer answers in."""
        raise NotImplementedError

    async def posts_in(self, space_id: uuid.UUID) -> bool:
        """Whether the writer may post in a channel of the space at all (the rights and
        the write scope are checked by the service besides)."""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class ToolContext(WriteContext):
    run: RunRef
    call: CallRef | None = None  # None only outside a run (a tool called directly)
    # The asking person released this call (`approvals/gate.py`): under the personal
    # mark it may write where others read (`writing.release_first`).
    released: bool = False
    # Under the personal mark, a call the gate found to change nothing (`update_page`'s
    # preview): it runs without a release, yet never writes (`writing.effect`), and
    # its result is the asker's alone like every event of a marked run (`runs.py`).
    previewing: bool = False

    @property
    def by(self) -> Authorship:
        """What the tool writes is written for the agent, naming the run."""
        return Authorship(Principal.agent(self.run.agent_id), self.run.id)

    @property
    def source(self) -> VersionSource:
        return VersionSource.AGENT

    def key(self, name: str, *parts: object) -> uuid.UUID:
        """Stable within the run, from the call's arguments."""
        return uuid.uuid5(self.run.id, ":".join([name, *map(str, parts)]))

    def binding(self) -> uuid.UUID:
        return self.run.id

    def answers_in(self, conversation_id: uuid.UUID) -> bool:
        return conversation_id == self.run.conversation_id

    async def posts_in(self, space_id: uuid.UUID) -> bool:
        """In a channel of a space the agent is a member of."""
        repo = AgentRepository(self.session, self.run.org_id)
        return space_id in await repo.member_space_ids(self.run.agent_id)


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
# The action a call needs, from its canonical arguments, for this actor (`action_of`).
ActionOf = Callable[[AsyncSession, Actor, dict[str, Any]], Awaitable[Action]]


@dataclass(frozen=True, slots=True)
class RemoteTool:
    """An external MCP server's tool behind a spec (plan M8 decision 8; ids and names
    only): the host calls it outside the step's transaction (`agents/external_step.py`)."""

    server_id: uuid.UUID
    tool_id: uuid.UUID
    server_name: str
    tool_name: str  # as the server names it
    writes: bool  # classified `write` by an admin: level 4, always a person's release


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """`level`: the lowest autonomy level (1 to 4) whose default allows the tool.
    `floor`: the loosest grant it can ever have (an external write tool: `confirm`).
    `explicit`: offered only to an agent with an entry for it (external tools).
    `remote`: an external tool (`run` is never called for it)."""

    name: str
    description: str
    args: type[BaseModel]
    run: Runner
    level: int = 1
    effect: Effect = Effect.READ
    subjects: Subjects | None = None  # None: the call changes no object (release: args)
    action: Action | None = None  # what the releasing person must be able to do there
    action_of: ActionOf | None = None  # instead of `action`, where the call decides it
    floor: Grant = Grant.ALLOW
    explicit: bool = False
    remote: RemoteTool | None = None

    async def needs(
        self, session: AsyncSession, actor: Actor, args: dict[str, Any]
    ) -> Action | None:
        """What `actor` must be able to do in each object's space to release the call."""
        if self.action_of is not None:
            return await self.action_of(session, actor, args)
        return self.action

"""Agents and runs as the API takes and shows them."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.modules.agents.models import (
    DEFAULT_LEVEL,
    MAX_INSTRUCTIONS_CHARS,
    MAX_INTRO_CHARS,
    MAX_LEVEL,
    MAX_NAME_CHARS,
    MAX_RUNTIME_SECONDS,
    MAX_STEPS,
    Agent,
    AgentStatus,
    EventKind,
    Run,
    RunState,
    StopReason,
)
from app.modules.agents.runs import ShownEvent
from app.modules.agents.toolbox.policy import Effect, Grant

if TYPE_CHECKING:  # grants.py imports the service, which imports these schemas
    from app.modules.agents.grants import AgentTools

Name = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MAX_NAME_CHARS,
        pattern=r"^[^\x00-\x1f\x7f]+$",
    ),
]
Intro = Annotated[str, StringConstraints(strip_whitespace=True, max_length=MAX_INTRO_CHARS)]
Instructions = Annotated[str, Field(max_length=MAX_INSTRUCTIONS_CHARS)]
ModelName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Steps = Annotated[int, Field(ge=1, le=MAX_STEPS)]
Runtime = Annotated[int, Field(ge=10, le=MAX_RUNTIME_SECONDS, description="seconds")]
Level = Annotated[
    int, Field(ge=1, le=MAX_LEVEL, description="autonomy level (spec 8.2); above 2: admins")
]


class AgentCreate(BaseModel):
    """`connection_id`/`model`: a chat connection of the organisation and one of its
    models. `responsible_user_id`: an active person (no guest) who answers for it."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    intro: Intro = ""
    instructions: Instructions = ""
    connection_id: uuid.UUID
    model: ModelName
    responsible_user_id: uuid.UUID
    status: AgentStatus = AgentStatus.DRAFT
    max_steps: Steps = MAX_STEPS
    max_runtime_seconds: Runtime = MAX_RUNTIME_SECONDS
    level: Level = DEFAULT_LEVEL


class AgentUpdate(BaseModel):
    """Fields left out stay as they are; `connection_id` and `model` go together."""

    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    intro: Intro | None = None
    instructions: Instructions | None = None
    connection_id: uuid.UUID | None = None
    model: ModelName | None = None
    responsible_user_id: uuid.UUID | None = None
    status: AgentStatus | None = None
    max_steps: Steps | None = None
    max_runtime_seconds: Runtime | None = None
    level: Level | None = None
    version: int


class AgentOut(BaseModel):
    """An agent as those with `agent.manage` see it; `responsible_name`: the
    responsible person's name."""

    id: uuid.UUID
    name: str
    intro: str
    instructions: str
    connection_id: uuid.UUID
    model: str
    responsible_user_id: uuid.UUID
    responsible_name: str | None
    status: AgentStatus
    max_steps: int
    max_runtime_seconds: int
    level: int
    version: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, agent: Agent, names: Mapping[uuid.UUID, str]) -> "AgentOut":
        return cls(
            id=agent.id,
            name=agent.name,
            intro=agent.intro,
            instructions=agent.instructions,
            connection_id=agent.connection_id,
            model=agent.model,
            responsible_user_id=agent.responsible_user_id,
            responsible_name=names.get(agent.id),
            status=agent.status,
            max_steps=agent.max_steps,
            max_runtime_seconds=agent.max_runtime_seconds,
            level=agent.level,
            version=agent.version,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


class AgentToolOut(BaseModel):
    """One tool of the catalog for this agent: its own `level` (the lowest that allows
    it) and `effect`; `default` (from the agent's level), `entry` (the agent's, or
    null) and `effective` (the stricter of both; what a run gets)."""

    name: str
    level: int
    effect: Effect
    default: Grant
    entry: Grant | None
    effective: Grant


class AgentToolsOut(BaseModel):
    """An agent's tool grants: every tool of the catalog (a fixed, short list, so not
    paged). `version`: the agent's."""

    agent_id: uuid.UUID
    level: int
    version: int
    tools: list[AgentToolOut]

    @classmethod
    def of(cls, shown: "AgentTools") -> "AgentToolsOut":
        return cls(
            agent_id=shown.agent.id,
            level=shown.agent.level,
            version=shown.agent.version,
            tools=[
                AgentToolOut(
                    name=t.name,
                    level=t.level,
                    effect=Effect(t.effect),
                    default=t.default,
                    entry=t.entry,
                    effective=t.effective,
                )
                for t in shown.tools
            ],
        )


class AgentToolEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    policy: Grant


class AgentToolsPut(BaseModel):
    """All of the agent's entries (those left out are removed); each can only tighten
    what the level allows. With the agent's `version`."""

    model_config = ConfigDict(extra="forbid")

    tools: Annotated[list[AgentToolEntry], Field(max_length=100)]
    version: int

    @field_validator("tools")
    @classmethod
    def _once_each(cls, tools: list[AgentToolEntry]) -> list[AgentToolEntry]:
        if len({t.tool for t in tools}) != len(tools):
            raise ValueError("each tool at most once")
        return tools


class AgentProfileOut(BaseModel):
    """What a person with `ai.use` learns of an agent to talk to: no instructions, no
    connection."""

    id: uuid.UUID
    name: str
    intro: str
    status: AgentStatus

    @classmethod
    def of(cls, agent: Agent) -> "AgentProfileOut":
        return cls(id=agent.id, name=agent.name, intro=agent.intro, status=agent.status)


class RunOut(BaseModel):
    """`steps`: model calls of the run; `attempt`: its take-ups by a worker;
    `wait_until`: while `waiting`, when it ends unanswered (`waiting_timeout`);
    `stop_reason` once `done`."""

    id: uuid.UUID
    agent_id: uuid.UUID
    conversation_id: uuid.UUID
    trigger_message_id: uuid.UUID
    state: RunState
    stop_reason: StopReason | None
    attempt: int
    steps: int
    wait_until: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def of(cls, run: Run) -> "RunOut":
        return cls(
            id=run.id,
            agent_id=run.agent_id,
            conversation_id=run.conversation_id,
            trigger_message_id=run.trigger_message_id,
            state=run.state,
            stop_reason=run.stop_reason,
            attempt=run.attempt,
            steps=run.steps,
            wait_until=run.wait_until,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


class RunEventOut(BaseModel):
    """One step of a run (model call: usage and the answer's parts; tool call: name,
    arguments, result, the spaces it came from; stop: the reason). `redacted`: parts
    the reader may not read are left out (`agents/runs.py`); the asking person always
    gets everything."""

    id: uuid.UUID
    attempt: int
    seq: int
    kind: EventKind
    content: dict[str, Any]
    redacted: bool
    created_at: datetime

    @classmethod
    def of(cls, shown: ShownEvent) -> "RunEventOut":
        event = shown.event
        return cls(
            id=event.id,
            attempt=event.attempt,
            seq=event.seq,
            kind=event.kind,
            content=shown.content,
            redacted=shown.redacted,
            created_at=event.created_at,
        )

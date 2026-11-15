"""Agents as the API takes and shows them (runs: `run_schemas.py`)."""

import uuid
from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

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
    AgentKind,
    AgentStatus,
)
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
    models. `responsible_user_id`: an active person (no guest) who answers for it.
    Both are needed for the organisation's agents (`agent.manage`). `personal`: the
    caller's own agent (`agent.create_personal`), which takes the caller's connection
    and model and has the caller as responsible person (given, they must be those).
    `kind: external` (plan M8 decision 11, `agent.manage`): an agent that works from
    outside through `/mcp`; no connection, no model, not personal, level at most 2
    (else 422 `agent.external_invalid`), a responsible person required."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    kind: AgentKind = AgentKind.INTERNAL
    intro: Intro = ""
    instructions: Instructions = ""
    personal: bool = False
    connection_id: uuid.UUID | None = None
    model: ModelName | None = None
    responsible_user_id: uuid.UUID | None = None
    status: AgentStatus = AgentStatus.DRAFT
    max_steps: Steps = MAX_STEPS
    max_runtime_seconds: Runtime = MAX_RUNTIME_SECONDS
    level: Level = DEFAULT_LEVEL


class AgentUpdate(BaseModel):
    """Fields left out stay as they are; `connection_id` and `model` go together. A
    personal agent takes its owner's connection and model anew with every change. The
    kind stays; an external agent takes no connection or model and no level above 2
    (422 `agent.external_invalid`)."""

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
    """An agent as those who manage it see it (`agent.manage`; a personal agent's
    owner); `responsible_name`: the responsible person's name; `owner_user_id`: a
    personal agent's owner (null: the organisation's). `kind`: `external` for an
    agent that works from outside through `/mcp` (plan M8): no connection or model
    (both null)."""

    id: uuid.UUID
    name: str
    kind: AgentKind
    intro: str
    instructions: str
    connection_id: uuid.UUID | None
    model: str | None
    responsible_user_id: uuid.UUID
    responsible_name: str | None
    owner_user_id: uuid.UUID | None
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
            kind=agent.kind,
            intro=agent.intro,
            instructions=agent.instructions,
            connection_id=agent.connection_id,
            model=agent.model,
            responsible_user_id=agent.responsible_user_id,
            responsible_name=names.get(agent.id),
            owner_user_id=agent.owner_user_id,
            status=agent.status,
            max_steps=agent.max_steps,
            max_runtime_seconds=agent.max_runtime_seconds,
            level=agent.level,
            version=agent.version,
            created_at=agent.created_at,
            updated_at=agent.updated_at,
        )


class AgentExternalToolOut(BaseModel):
    """What an external tool is (plan M8 decision 8): its server and its name there;
    `usable`: approved, unchanged and on an enabled server (else a run never gets it,
    whatever the entry says)."""

    server_id: uuid.UUID
    server_name: str
    tool_id: uuid.UUID
    tool_name: str
    usable: bool


class AgentToolOut(BaseModel):
    """One tool for this agent: its own `level` (the lowest that allows it) and
    `effect`; `default` (from the agent's level; an external tool's is `block`: it
    needs an entry), `entry` (the agent's, or null) and `effective` (what a run gets).
    `external`: set for an external MCP server's tool (name `ext_…`; a write tool is
    level 4 and at most `confirm`), null for the catalog's. `via_mcp`: only for an
    external agent (plan M8): the catalog tool can reach its token over `/mcp` (offered
    there, level 2 at most); false for every other agent and tool."""

    name: str
    level: int
    effect: Effect
    default: Grant
    entry: Grant | None
    effective: Grant
    external: AgentExternalToolOut | None = None
    via_mcp: bool = False


class AgentToolsOut(BaseModel):
    """An agent's tool grants: every tool of the catalog (a fixed, short list, so not
    paged), then the organisation's usable external tools and those with an entry
    (approved ones only, at most `mcp_servers/tools.MAX_APPROVED_TOOLS` of them, plus at
    most 100 entries: a hard cap instead of pages, as the list is one versioned
    document the PUT replaces whole). `version`: the agent's.
    `max_level`: the highest level the caller may give the agent (above 2: admins
    only)."""

    agent_id: uuid.UUID
    level: int
    max_level: int
    version: int
    tools: list[AgentToolOut]

    @classmethod
    def of(cls, shown: "AgentTools") -> "AgentToolsOut":
        return cls(
            agent_id=shown.agent.id,
            level=shown.agent.level,
            max_level=shown.max_level,
            version=shown.agent.version,
            tools=[
                AgentToolOut(
                    name=t.name,
                    level=t.level,
                    effect=Effect(t.effect),
                    default=t.default,
                    entry=t.entry,
                    effective=t.effective,
                    external=(
                        AgentExternalToolOut(
                            server_id=t.external.server_id,
                            server_name=t.external.server_name,
                            tool_id=t.external.tool_id,
                            tool_name=t.external.tool_name,
                            usable=t.external.usable,
                        )
                        if t.external
                        else None
                    ),
                    via_mcp=t.via_mcp,
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
    connection. `kind`: `external` for one that works from outside (plan M8): it
    answers no message here."""

    id: uuid.UUID
    name: str
    kind: AgentKind
    intro: str
    status: AgentStatus

    @classmethod
    def of(cls, agent: Agent) -> "AgentProfileOut":
        return cls(
            id=agent.id, name=agent.name, kind=agent.kind, intro=agent.intro, status=agent.status
        )

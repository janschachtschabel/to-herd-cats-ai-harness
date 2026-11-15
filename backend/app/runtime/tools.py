"""Tools as the model sees them: their definitions and the checking of the arguments
it sends. Which tools a run offers, and what they do, the executor decides
(`modules/agents/toolbox/`): it gives the loop the tools to offer, and only those can
be called; a name the loop was not given is a bad call, never run."""

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from pydantic_ai.tools import ToolDefinition


class ToolSchema(Protocol):
    """What the loop needs of a tool: its name, what it does, its arguments' model."""

    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...
    @property
    def args(self) -> type[BaseModel]: ...


def definitions(schemas: Sequence[ToolSchema]) -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name=schema.name,
            description=schema.description,
            parameters_json_schema=schema.args.model_json_schema(),
            strict=False,
        )
        for schema in schemas
    ]


class BadToolCall(Exception):  # noqa: N818 (a verdict)
    """The model called a tool it was not offered or sent arguments that do not fit."""


def parse(offered: Mapping[str, ToolSchema], name: str, raw: str | dict[str, Any] | None) -> Any:
    """The call's arguments as its tool's model (a `BaseModel`)."""
    schema = offered.get(name)
    if schema is None:
        raise BadToolCall(f"unknown tool {name!r}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        return schema.args.model_validate(data)
    except (ValueError, ValidationError):
        raise BadToolCall(f"arguments of {name} do not fit its schema") from None


def signature(name: str, args: BaseModel) -> str:
    """The same for the same call, whatever the JSON's spacing or key order (for the
    `no_progress` stop: a third identical call)."""
    return f"{name}:{args.model_dump_json()}"

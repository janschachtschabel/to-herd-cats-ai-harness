"""The tools of a level-1 agent (plan M5 decision 4): `search`, `read_page`,
`read_ticket`, read only. Here only their definitions for the model and the checking
of the arguments it sends; the executor runs them through the services, with the
run's actor (`modules/agents/tools.py`)."""

import json
import uuid
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError
from pydantic_ai.tools import ToolDefinition


class SearchArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ReadPageArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_id: uuid.UUID


class ReadTicketArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]


ToolArgs = SearchArgs | ReadPageArgs | ReadTicketArgs

_ARGS: dict[str, type[BaseModel]] = {
    "search": SearchArgs,
    "read_page": ReadPageArgs,
    "read_ticket": ReadTicketArgs,
}
_DESCRIPTIONS = {
    "search": (
        "Full-text search in the wiki pages and tickets you may read. Returns the best "
        "hits with type, id or key, title, space and a short snippet."
    ),
    "read_page": "Read one wiki page by its id (from a search hit). Returns its Markdown.",
    "read_ticket": "Read one ticket by its key (such as HC-12). Returns its fields and text.",
}


def definitions() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name=name,
            description=_DESCRIPTIONS[name],
            parameters_json_schema=args.model_json_schema(),
            strict=False,
        )
        for name, args in _ARGS.items()
    ]


class BadToolCall(Exception):  # noqa: N818 (a verdict)
    """The model called an unknown tool or sent arguments that do not fit."""


def parse(name: str, raw: str | dict[str, Any] | None) -> ToolArgs:
    model = _ARGS.get(name)
    if model is None:
        raise BadToolCall(f"unknown tool {name!r}")
    try:
        data = json.loads(raw) if isinstance(raw, str) else (raw or {})
        parsed = model.model_validate(data)
    except (ValueError, ValidationError):
        raise BadToolCall(f"arguments of {name} do not fit its schema") from None
    assert isinstance(parsed, SearchArgs | ReadPageArgs | ReadTicketArgs)
    return parsed


def signature(name: str, args: ToolArgs) -> str:
    """The same for the same call, whatever the JSON's spacing or key order (for the
    `no_progress` stop: a third identical call)."""
    return f"{name}:{args.model_dump_json()}"

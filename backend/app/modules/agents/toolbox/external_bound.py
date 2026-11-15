"""The bound on what one agent's external tools add to every model call (module review
M8 2, finding G5). Each tool is bounded on its own (`external.py`, `schema_view.py`);
in sum an agent with many entries could still send a megabyte of definitions with
every call. `MAX_DEFINITION_CHARS` bounds the sum: the agent's offered external tools
are taken in name order (`ext_<tool id>_…`, the id a UUIDv7: the order they were
listed in), each as long as the sum stays within the bound; one that does not fit is
left out, and the next smaller ones may still fit. The same tools and grants give the
same choice at every step, every take-up and on replay. The agent's grants view says
which are left out (`grants.py`), and the worker counts them without names
(`external_metrics.count_left_out`)."""

import json
from collections.abc import Iterable

from app.modules.agents.toolbox.base import ToolSpec

MAX_DEFINITION_CHARS = 100_000


def definition_chars(spec: ToolSpec) -> int:
    """What a tool's definition adds to a model call: its name, its description and
    its arguments' schema (as JSON)."""
    schema = json.dumps(spec.args.model_json_schema(), ensure_ascii=False)
    return len(spec.name) + len(spec.description) + len(schema)


def left_out(external: Iterable[ToolSpec]) -> set[str]:
    """The names of the offered external tools that the bound leaves out."""
    total, dropped = 0, set()
    for spec in sorted(external, key=lambda s: s.name):
        size = definition_chars(spec)
        if total + size > MAX_DEFINITION_CHARS:
            dropped.add(spec.name)
        else:
            total += size
    return dropped


def bounded(tools: list[ToolSpec]) -> tuple[list[ToolSpec], int]:
    """A run's tools without the external ones the bound leaves out, and how many."""
    dropped = left_out(t for t in tools if t.remote is not None)
    return [t for t in tools if t.name not in dropped], len(dropped)

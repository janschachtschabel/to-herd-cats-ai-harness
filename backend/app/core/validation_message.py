"""The message of a 422: where the request was wrong, never what it said.

A validation error's location mixes the API's own names (`body`, `locale`, `limit`)
with names the client chose: the key of an unknown field, a key in a free mapping.
Only the API's own vocabulary is named, the field names of its OpenAPI document and its
parameters; anything else is `*`, a list position its number (ASVS 5.0 V16.5.1,
`test_error_bodies_never_echo_input`).
"""

from collections.abc import Iterable, Sequence
from typing import Any

from fastapi import FastAPI

_PLACES = frozenset({"body", "query", "path", "header", "cookie"})


def vocabulary(app: FastAPI) -> frozenset[str]:
    """Every field and parameter name of the app's OpenAPI document (once per app)."""
    known: frozenset[str] | None = getattr(app.state, "error_vocabulary", None)
    if known is None:
        names = set(_PLACES)
        document = app.openapi()
        for schema in document.get("components", {}).get("schemas", {}).values():
            names.update(schema.get("properties", {}))
        for operations in document.get("paths", {}).values():
            for operation in operations.values():
                if isinstance(operation, dict):
                    names.update(p["name"] for p in operation.get("parameters", []))
        known = app.state.error_vocabulary = frozenset(names)
    return known


def _place(loc: Sequence[Any], known: frozenset[str]) -> str:
    return ".".join(str(part) if isinstance(part, int) or part in known else "*" for part in loc)


def validation_message(errors: Iterable[dict[str, Any]], known: frozenset[str]) -> str:
    places = dict.fromkeys(_place(e["loc"], known) for e in errors if e.get("loc"))
    return f"Invalid request: {', '.join(places)}" if places else "Invalid request"

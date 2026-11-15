"""What of a tool's input schema may reach a model (module review M8 1, finding 2).

Every word of an input schema is the server's, as untrusted as its description:
property descriptions, titles, enums, defaults, examples, patterns. So the model is
offered only the schema's **structure** (`structure`): types, property names, what is
required, items, nesting, numeric and length bounds and well-known formats. The
server's words about the arguments (`words`: per property its description, title,
allowed values and default, each cut) go into the tool's description, framed as
untrusted and cut as a whole (`toolbox/external.py`).

A schema that cannot be offered that way has a `problem`, found at refresh (stored
on the tool, shown to the admin, the tool cannot be approved) and again before a run
offers it (rows stored before this rule): over `MAX_SCHEMA_BYTES` as JSON (then not
even stored whole, `stored`), a structure over `MAX_STRUCTURE_CHARS`, deeper than
`MAX_DEPTH` (`schema_unsupported`), or a property name outside `NAME`
(`schema_property_names`).

Property names are the one word of the server's that reaches the model unframed: a
name is the argument's name, offered as it is. So they keep to a strict charset and
length (module review M8 2, finding G4): a letter or `_`, then letters, digits and
`_`, at most `MAX_NAME_CHARS`. What is left: a name within those bounds (say
`ignore_rules`) is still the server's word; the admin's approval, which shows the
schema, is the control for it.
"""

import json
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

MAX_SCHEMA_BYTES = 64 * 1024
MAX_STRUCTURE_CHARS = 8_000
MAX_DEPTH = 8
MAX_WORD_CHARS = 300  # one property's words
MAX_WORDS_CHARS = 2_000  # all of them (the frame cuts nothing more)
MAX_NAME_CHARS = 32
NAME = re.compile(rf"[A-Za-z_][A-Za-z0-9_]{{0,{MAX_NAME_CHARS - 1}}}")
OBJECT: dict[str, Any] = {"type": "object"}

_TYPES = {"object", "array", "string", "number", "integer", "boolean", "null"}
_FORMATS = {"date-time", "date", "time", "email", "uri", "uuid", "ipv4", "ipv6", "hostname"}
_BOUNDS = (
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
)
_UNIONS = ("anyOf", "oneOf", "allOf")


class SchemaProblem(StrEnum):
    TOO_LARGE = "schema_too_large"
    UNSUPPORTED = "schema_unsupported"
    NAMES = "schema_property_names"  # a property name outside `NAME`


@dataclass(slots=True)
class View:
    structure: dict[str, Any] = field(default_factory=lambda: dict(OBJECT))
    words: str = ""
    problem: SchemaProblem | None = None


class _Unsupported(Exception):
    pass


class _BadName(Exception):
    pass


def size_of(schema: Any) -> int:
    return len(json.dumps(schema, ensure_ascii=False, separators=(",", ":")).encode())


def stored(schema: dict[str, Any]) -> dict[str, Any]:
    """What is kept of a listed schema: itself, or nothing over `MAX_SCHEMA_BYTES`."""
    return schema if size_of(schema) <= MAX_SCHEMA_BYTES else dict(OBJECT)


def view(schema: Any) -> View:
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return View()  # any object: nothing of the server's to show
    if size_of(schema) > MAX_SCHEMA_BYTES:
        return View(problem=SchemaProblem.TOO_LARGE)
    words: list[str] = []
    try:
        structure = _structure(schema, "", words, 0)
    except _Unsupported:
        return View(problem=SchemaProblem.UNSUPPORTED)
    except _BadName:
        return View(problem=SchemaProblem.NAMES)
    if size_of(structure) > MAX_STRUCTURE_CHARS:
        return View(problem=SchemaProblem.TOO_LARGE)
    return View(structure, "\n".join(words)[:MAX_WORDS_CHARS])


def problem_of(schema: Any) -> SchemaProblem | None:
    return view(schema).problem


def _structure(node: Any, path: str, words: list[str], depth: int) -> dict[str, Any]:
    if depth > MAX_DEPTH:
        raise _Unsupported
    if not isinstance(node, dict):
        return {}
    _note(node, path, words)
    out: dict[str, Any] = {}
    kind = node.get("type")
    if isinstance(kind, str) and kind in _TYPES:
        out["type"] = kind
    elif isinstance(kind, list) and kind and all(k in _TYPES for k in kind):
        out["type"] = list(kind)
    if isinstance(node.get("format"), str) and node["format"] in _FORMATS:
        out["format"] = node["format"]
    for bound in _BOUNDS:
        value = node.get(bound)
        if isinstance(value, int | float) and not isinstance(value, bool):
            out[bound] = value
    properties = node.get("properties")
    if isinstance(properties, dict):
        if not all(NAME.fullmatch(name) for name in properties):
            raise _BadName
        out["properties"] = {
            name: _structure(sub, f"{path}.{name}" if path else name, words, depth + 1)
            for name, sub in properties.items()
        }
        required = node.get("required")
        if isinstance(required, list):
            out["required"] = [r for r in required if isinstance(r, str) and r in properties]
    extra = node.get("additionalProperties")
    if isinstance(extra, bool):
        out["additionalProperties"] = extra
    elif isinstance(extra, dict):
        out["additionalProperties"] = _structure(extra, f"{path}.*", words, depth + 1)
    if isinstance(node.get("items"), dict):
        out["items"] = _structure(node["items"], f"{path}[]", words, depth + 1)
    for union in _UNIONS:
        options = node.get(union)
        if isinstance(options, list):
            out[union] = [_structure(o, path, words, depth + 1) for o in options]
    return out


def _note(node: dict[str, Any], path: str, words: list[str]) -> None:
    """The server's words about one property, cut, for the framed description."""
    said: list[str] = []
    for key in ("title", "description"):
        if isinstance(node.get(key), str) and node[key].strip():
            said.append(" ".join(node[key].split()))
    if isinstance(node.get("enum"), list):
        said.append("one of: " + ", ".join(_word(v) for v in node["enum"]))
    if "const" in node:
        said.append("always: " + _word(node["const"]))
    if "default" in node:
        said.append("default: " + _word(node["default"]))
    if isinstance(node.get("examples"), list):
        said.append("e.g. " + ", ".join(_word(v) for v in node["examples"]))
    if isinstance(node.get("pattern"), str):
        said.append("pattern: " + node["pattern"])
    if said:
        words.append(f"{path or '(arguments)'}: {'; '.join(said)}"[:MAX_WORD_CHARS])


def _word(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)

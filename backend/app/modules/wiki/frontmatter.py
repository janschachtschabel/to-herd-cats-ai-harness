"""Front matter of exported and imported Markdown: a `---` block of `key: value` lines.

Written as a subset of YAML that JSON can read too: every string in double quotes,
lists in brackets (`tags: ["a", "b, c"]`), so names with commas, quotes or colons
survive. Read are that form and the plain one other tools write (`title: Handbuch`,
`tags: [a, b]`); nested YAML is not understood and such keys are ignored.
"""

import json
import re

FENCE = "---"
_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$")

Meta = dict[str, str | list[str]]


def serialise(meta: Meta, body: str) -> str:
    lines = [FENCE]
    for key, value in meta.items():
        lines.append(f"{key}: {json.dumps(value, ensure_ascii=False)}")
    lines.append(FENCE)
    return "\n".join(lines) + "\n" + body


def parse(text: str) -> tuple[Meta, str]:
    """(metadata, body). Without a front matter block, the metadata is empty and the
    body is the whole text."""
    normalised = text.removeprefix("﻿")
    first, newline, rest = normalised.partition("\n")
    if first.rstrip("\r") != FENCE or not newline:
        return {}, text
    meta: Meta = {}
    offset = 0
    for line in rest.splitlines(keepends=True):
        offset += len(line)
        stripped = line.rstrip("\r\n")
        if stripped == FENCE:
            return meta, rest[offset:]
        match = _LINE.match(stripped)
        if match:
            value = _value(match.group(2).strip())
            if value is not None:
                meta[match.group(1)] = value
    return {}, text  # never closed: not front matter


def _value(raw: str) -> str | list[str] | None:
    if raw.startswith(("[", '"')):
        try:
            parsed = json.loads(raw)
        except ValueError:
            parsed = None
        if isinstance(parsed, str):
            return parsed
        if isinstance(parsed, list):
            return [str(item) for item in parsed if isinstance(item, str | int | float)]
        if raw.startswith("["):
            if not raw.endswith("]"):
                return None
            return [_unquote(item) for item in _flow_items(raw[1:-1]) if item.strip()]
    if raw.startswith("{") or raw in ("|", ">"):
        return None  # nested or block YAML: not understood
    return _unquote(raw)


def _flow_items(inner: str) -> list[str]:
    """`a, "b, c", 'd'` → the items, split at commas outside quotes."""
    items: list[str] = []
    current: list[str] = []
    quote = ""
    for char in inner:
        if quote:
            quote = "" if char == quote and (not current or current[-1] != "\\") else quote
        elif char in "\"'":
            quote = char
        elif char == ",":
            items.append("".join(current))
            current = []
            continue
        current.append(char)
    items.append("".join(current))
    return items


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"')
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value

"""The SKILL.md format (agentskills.io; plan M6 decision 11) and the bounds of a skill.

A SKILL.md is YAML front matter between two `---` lines, then the instructions in
Markdown. The front matter is read strictly: a mapping of the format's fields only,
`name` (1 to 64 lowercase letters, digits and single hyphens, not at either end) and
`description` (text, 1 to 1,024 characters) required; the format's optional fields
(`license`, `compatibility`, `metadata`, `allowed-tools`) are accepted when well formed
but not kept (they mean nothing here; the caller reports them as ignored). YAML is read
with the safe loader, without aliases, and only up to `MAX_FRONTMATTER_CHARS`.

A skill is text: nothing in it is ever executed (no tool runs code in v1).
"""

import re
from dataclasses import dataclass, field
from typing import Any

import yaml

MAX_NAME_CHARS = 64
MAX_DESCRIPTION_CHARS = 1024
MAX_CONTENT_CHARS = 50_000
MAX_FRONTMATTER_CHARS = 8 * 1024
FILENAME = "SKILL.md"

_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_FENCE = "---"
_OPTIONAL = {"license": str, "compatibility": str, "metadata": dict, "allowed-tools": str}
_REQUIRED = ("name", "description")


class SkillFormatError(ValueError):
    """Why a text is no valid skill: `reason` is the code reported for it."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class ParsedSkill:
    name: str
    description: str
    content: str
    ignored: list[str] = field(default_factory=list)  # optional fields not kept, sorted


def valid_name(name: str) -> bool:
    return len(name) <= MAX_NAME_CHARS and _NAME.fullmatch(name) is not None


def checked_description(value: object) -> str:
    if not isinstance(value, str):
        raise SkillFormatError("description_invalid")
    text = value.strip()
    if not text or len(text) > MAX_DESCRIPTION_CHARS or "\x00" in text:
        raise SkillFormatError("description_invalid")
    return text


def checked_content(value: str) -> str:
    if not value.strip() or len(value) > MAX_CONTENT_CHARS or "\x00" in value:
        raise SkillFormatError("content_invalid")
    return value


def checked_name(value: object) -> str:
    if not isinstance(value, str) or not valid_name(value):
        raise SkillFormatError("name_invalid")
    return value


class _Loader(yaml.SafeLoader):  # type: ignore[misc]  # PyYAML ships no types
    """The safe loader without aliases (no shared or expanding structures)."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("aliases are not accepted")
        return super().compose_node(parent, index)


def _split(text: str) -> tuple[str, str]:
    """(front matter, body); the body starts after the closing fence's line."""
    normalised = text.removeprefix("﻿")
    first, newline, rest = normalised.partition("\n")
    if first.rstrip("\r") != _FENCE or not newline:
        raise SkillFormatError("frontmatter_invalid")
    offset = 0
    for line in rest.splitlines(keepends=True):
        if line.rstrip("\r\n") == _FENCE:
            return rest[:offset], rest[offset + len(line) :]
        offset += len(line)
        if offset > MAX_FRONTMATTER_CHARS:
            break
    raise SkillFormatError("frontmatter_invalid")


def _meta(block: str) -> dict[str, Any]:
    try:
        meta = yaml.load(block, Loader=_Loader)  # noqa: S506 -- a SafeLoader subclass
    except yaml.YAMLError:
        raise SkillFormatError("frontmatter_invalid") from None
    if not isinstance(meta, dict) or not all(isinstance(k, str) for k in meta):
        raise SkillFormatError("frontmatter_invalid")
    if set(meta) - set(_REQUIRED) - set(_OPTIONAL):
        raise SkillFormatError("frontmatter_invalid")
    for key, kind in _OPTIONAL.items():
        if key in meta and not isinstance(meta[key], kind):
            raise SkillFormatError("frontmatter_invalid")
    metadata = meta.get("metadata", {})
    if not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()):
        raise SkillFormatError("frontmatter_invalid")
    return meta


def parse_skill_md(text: str) -> ParsedSkill:
    """The skill a SKILL.md describes; `SkillFormatError` with the reason otherwise."""
    block, body = _split(text)
    meta = _meta(block)
    return ParsedSkill(
        name=checked_name(meta.get("name")),
        description=checked_description(meta.get("description")),
        content=checked_content(body),
        ignored=sorted(set(meta) & set(_OPTIONAL)),
    )


def serialise_skill_md(name: str, description: str, content: str) -> str:
    """A SKILL.md that `parse_skill_md` reads back as the same skill."""
    meta = yaml.safe_dump(
        {"name": name, "description": description},
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=10_000,
    )
    return f"{_FENCE}\n{meta}{_FENCE}\n{content}"

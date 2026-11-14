import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.principal import PrincipalType
from app.modules.wiki.diffing import Diff, HunkKind
from app.modules.wiki.models import MAX_LABEL_CHARS, VersionSource
from app.modules.wiki.versions_repository import NamedVersion

Label = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_LABEL_CHARS)
]


class VersionAuthor(BaseModel):
    """`name` is None for an author that is not a person."""

    type: PrincipalType
    id: uuid.UUID
    name: str | None


class VersionSummaryOut(BaseModel):
    """`change_summary` is free text, or `restore:<n>` for a version that brought
    version n back (the client words it). `ai`: written for an agent (the AI mark,
    spec 9: its author is an agent); `run_id`: the agent's run that wrote it."""

    number: int
    title: str
    author: VersionAuthor
    source: VersionSource
    change_summary: str | None
    label: str | None
    created_at: datetime
    ai: bool
    run_id: uuid.UUID | None

    @classmethod
    def of(cls, row: NamedVersion) -> "VersionSummaryOut":
        v = row.version
        return cls(
            number=v.number,
            title=v.title,
            author=VersionAuthor(type=v.author_type, id=v.author_id, name=row.author_name),
            source=v.source,
            change_summary=v.change_summary,
            label=v.label,
            created_at=v.created_at,
            ai=v.author_type == PrincipalType.AGENT,
            run_id=v.run_id,
        )


class VersionOut(VersionSummaryOut):
    content_md: str

    @classmethod
    def of(cls, row: NamedVersion) -> "VersionOut":
        summary = VersionSummaryOut.of(row)
        return cls(**summary.model_dump(), content_md=row.version.content_md)


class VersionLabelIn(BaseModel):
    """null takes the label away."""

    model_config = ConfigDict(extra="forbid")

    label: Label | None


class HunkOut(BaseModel):
    kind: HunkKind
    lines: list[str]


class DiffOut(BaseModel):
    """Line by line from `from_number` to `to_number`; a changed line is a `delete`
    followed by an `insert`."""

    from_number: int
    to_number: int
    title_changed: bool
    from_title: str
    to_title: str
    hunks: list[HunkOut]

    @classmethod
    def of(cls, from_number: int, to_number: int, diff: Diff) -> "DiffOut":
        return cls(
            from_number=from_number,
            to_number=to_number,
            title_changed=diff.title_changed,
            from_title=diff.from_title,
            to_title=diff.to_title,
            hunks=[HunkOut(kind=h.kind, lines=h.lines) for h in diff.hunks],
        )

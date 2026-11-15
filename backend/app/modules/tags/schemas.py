import uuid
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

from app.modules.tags.models import MAX_TAG_NAME_CHARS, Tag

MAX_TAGS_PER_SUBJECT = 50
DEFAULT_COLOR = "#64748b"

TagName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TAG_NAME_CHARS)
]
# `#rrggbb`, stored in lower case.
Color = Annotated[
    str,
    StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$"),
    AfterValidator(str.lower),
]


class TagOut(BaseModel):
    """`space_id` null: a system-wide tag."""

    id: uuid.UUID
    space_id: uuid.UUID | None
    name: str
    color: str
    version: int

    @classmethod
    def of(cls, tag: Tag) -> "TagOut":
        return cls(
            id=tag.id, space_id=tag.space_id, name=tag.name, color=tag.color, version=tag.version
        )


class TagCreate(BaseModel):
    """Without `space_id` a system-wide tag (`tag.manage`); with one, a tag of that
    space (`page.moderate` there)."""

    model_config = ConfigDict(extra="forbid")

    name: TagName
    color: Color = DEFAULT_COLOR
    space_id: uuid.UUID | None = None


class TagUpdate(BaseModel):
    """Fields left out stay as they are; neither may be null. A tag keeps its scope."""

    model_config = ConfigDict(extra="forbid")

    name: TagName | None = None
    color: Color | None = None
    version: int

    @field_validator("name", "color")
    @classmethod
    def _not_null(cls, value: str | None) -> str:
        # Runs only for a field the client sent.
        if value is None:
            raise ValueError("cannot be null")
        return value


class TagsSet(BaseModel):
    """The object's tags from now on (the set replaces the old one); `version` is the
    page version the client read."""

    model_config = ConfigDict(extra="forbid")

    tag_ids: list[uuid.UUID] = Field(max_length=MAX_TAGS_PER_SUBJECT)
    version: int

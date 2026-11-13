import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.core.principal import PrincipalType
from app.modules.wiki.models import MAX_CONTENT_CHARS, MAX_TITLE_CHARS, Page, PageStatus

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TITLE_CHARS)
]
Markdown = Annotated[str, Field(max_length=MAX_CONTENT_CHARS)]


class PrincipalRef(BaseModel):
    type: PrincipalType
    id: uuid.UUID


class PageOut(BaseModel):
    """`version` guards writes (send it back; stale → 409). `collab_generation` changes
    whenever open live-editing sessions of the page end."""

    id: uuid.UUID
    space_id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str
    slug: str
    path: str
    sort_order: int
    content_md: str
    status: PageStatus
    version: int
    collab_generation: int
    created_by: PrincipalRef
    updated_by: PrincipalRef
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None

    @classmethod
    def of(cls, page: Page) -> "PageOut":
        return cls(
            id=page.id,
            space_id=page.space_id,
            parent_id=page.parent_id,
            title=page.title,
            slug=page.slug,
            path=page.path,
            sort_order=page.sort_order,
            content_md=page.content_md,
            status=page.status,
            version=page.version,
            collab_generation=page.collab_generation,
            created_by=PrincipalRef(type=page.created_by_type, id=page.created_by_id),
            updated_by=PrincipalRef(type=page.updated_by_type, id=page.updated_by_id),
            created_at=page.created_at,
            updated_at=page.updated_at,
            published_at=page.published_at,
        )


class TreeNodeOut(BaseModel):
    """A page in the flat tree: nest by `parent_id`, order siblings by `sort_order`."""

    id: uuid.UUID
    parent_id: uuid.UUID | None
    title: str
    slug: str
    path: str
    status: PageStatus
    sort_order: int

    @classmethod
    def of(cls, page: Page) -> "TreeNodeOut":
        return cls(
            id=page.id,
            parent_id=page.parent_id,
            title=page.title,
            slug=page.slug,
            path=page.path,
            status=page.status,
            sort_order=page.sort_order,
        )


class PageCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Title
    parent_id: uuid.UUID | None = None
    content_md: Markdown = ""


class PageUpdate(BaseModel):
    """Fields left out stay as they are; neither may be null."""

    model_config = ConfigDict(extra="forbid")

    title: Title | None = None
    content_md: Markdown | None = None
    version: int

    @field_validator("title", "content_md")
    @classmethod
    def _not_null(cls, value: str | None) -> str:
        # Runs only for a field the client sent.
        if value is None:
            raise ValueError("cannot be null")
        return value


class ExpectedVersion(BaseModel):
    """The page version the client read (stale → 409 `page.version_conflict`)."""

    model_config = ConfigDict(extra="forbid")

    version: int

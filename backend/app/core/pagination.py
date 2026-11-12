"""Keyset pagination: opaque cursors over (created_at, id), or over id alone.

Ids are UUIDv7 and therefore ordered by creation time; tables without `created_at`
page by id.
"""

import base64
import binascii
import uuid
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.errors import ValidationFailed


class PageParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = None


class Page[T](BaseModel):
    # Services return pages of ORM rows; routers turn them into pages of schemas.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    items: list[T]
    next_cursor: str | None = None


def encode_cursor(created_at: datetime, id_: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{id_}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, id_ = raw.split("|")
        return datetime.fromisoformat(ts), uuid.UUID(id_)
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise ValidationFailed("Invalid cursor", code="validation_failed") from exc


def encode_id_cursor(id_: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(id_.bytes).decode().rstrip("=")


def decode_id_cursor(cursor: str) -> uuid.UUID:
    try:
        return uuid.UUID(bytes=base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
    except (binascii.Error, ValueError) as exc:
        raise ValidationFailed("Invalid cursor", code="validation_failed") from exc


def id_page[T](rows: list[T], limit: int, key: Callable[[T], uuid.UUID]) -> Page[T]:
    """`rows` were fetched with `limit + 1`: the extra row tells whether there is more."""
    items = rows[:limit]
    more = len(rows) > limit
    return Page[T](items=items, next_cursor=encode_id_cursor(key(items[-1])) if more else None)

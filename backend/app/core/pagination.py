"""Keyset pagination: opaque cursors over (created_at, id)."""

import base64
import binascii
import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.errors import ValidationFailed


class PageParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = None


class Page[T](BaseModel):
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

"""Keyset pagination: opaque cursors over (created_at, id), over (text key, id), over
(score, id) for ranked results, over (id key, id) or over id alone.

Ids are UUIDv7 and therefore ordered by creation time; tables without `created_at`
page by id. Lists sorted by name page by (key, id).
"""

import base64
import json
import math
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

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


def _invalid(exc: Exception | None = None) -> ValidationFailed:
    error = ValidationFailed("Invalid cursor", code="validation_failed")
    error.__cause__ = exc
    return error


def _b64(cursor: str) -> bytes:
    return base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))


def _storable(text: str) -> str:
    """Text the database can take: valid UTF-8 (no lone surrogate), no NUL."""
    text.encode("utf-8")
    if "\x00" in text:
        raise ValueError("NUL in cursor text")
    return text


# A cursor is untrusted input: any failure while decoding it (bad base64, bad UTF-8,
# wrong JSON types, out-of-range dates, absurd numbers, deep nesting) means "invalid
# cursor", answered with 422, never a 500.


def encode_cursor(created_at: datetime, id_: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{id_}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """An aware timestamp, normalised to UTC (an offset that leaves the date range
    fails here, not in the database), and an id."""
    try:
        ts, id_ = _b64(cursor).decode().split("|")
        created_at = datetime.fromisoformat(ts)
        if created_at.tzinfo is None:
            raise ValueError("naive timestamp")
        return created_at.astimezone(UTC), uuid.UUID(id_)
    except Exception as exc:
        raise _invalid(exc) from exc


def encode_tagged_cursor(moment: datetime, id_: uuid.UUID, tag: str) -> str:
    """A (timestamp, id) cursor that also holds a text the list compares on the next
    page (the event window's viewer zone)."""
    raw = json.dumps([moment.isoformat(), str(id_), tag]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_tagged_cursor(cursor: str) -> tuple[datetime, uuid.UUID, str]:
    """`decode_cursor`'s timestamp and id, and the tag."""
    try:
        moment, id_, tag = json.loads(_b64(cursor).decode())
        if not all(isinstance(part, str) for part in (moment, id_, tag)):
            raise TypeError("cursor parts are not text")
        at = datetime.fromisoformat(moment)
        if at.tzinfo is None:
            raise ValueError("naive timestamp")
        return at.astimezone(UTC), uuid.UUID(id_), _storable(tag)
    except Exception as exc:
        raise _invalid(exc) from exc


def encode_id_cursor(id_: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(id_.bytes).decode().rstrip("=")


def decode_id_cursor(cursor: str) -> uuid.UUID:
    """Any 16 bytes are a position (ids are opaque); anything else is invalid."""
    try:
        return uuid.UUID(bytes=_b64(cursor))
    except Exception as exc:
        raise _invalid(exc) from exc


def encode_id_pair_cursor(first: uuid.UUID, second: uuid.UUID) -> str:
    """Two ids: a sort key that is itself an id (UUIDv7) and the row's id."""
    return base64.urlsafe_b64encode(first.bytes + second.bytes).decode().rstrip("=")


def decode_id_pair_cursor(cursor: str) -> tuple[uuid.UUID, uuid.UUID]:
    try:
        raw = _b64(cursor)
        if len(raw) != 32:
            raise ValueError("not two ids")
        return uuid.UUID(bytes=raw[:16]), uuid.UUID(bytes=raw[16:])
    except Exception as exc:
        raise _invalid(exc) from exc


def encode_key_cursor(key: str, id_: uuid.UUID) -> str:
    raw = json.dumps([key, str(id_)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_key_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    try:
        key, id_ = json.loads(_b64(cursor).decode())
        if not isinstance(key, str) or not isinstance(id_, str):
            raise TypeError("cursor parts are not text")
        return _storable(key), uuid.UUID(id_)
    except Exception as exc:
        raise _invalid(exc) from exc


def encode_score_cursor(score: float, id_: uuid.UUID) -> str:
    raw = json.dumps([score, str(id_)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_score_cursor(cursor: str) -> tuple[float, uuid.UUID]:
    """A finite number (no NaN, no infinity) and an id."""
    try:
        score, id_ = json.loads(_b64(cursor).decode())
        if isinstance(score, bool) or not isinstance(score, int | float):
            raise TypeError("score is not a number")
        if not isinstance(id_, str) or not math.isfinite(score):
            raise ValueError("bad score cursor")
        return float(score), uuid.UUID(id_)
    except Exception as exc:
        raise _invalid(exc) from exc


def encode_parts_cursor(*parts: str) -> str:
    """A cursor of several texts (the list parses them); `decode_parts_cursor` reads
    exactly that many back."""
    raw = json.dumps(list(parts)).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_parts_cursor(cursor: str, count: int) -> list[str]:
    try:
        parts = json.loads(_b64(cursor).decode())
        if not isinstance(parts, list) or len(parts) != count:
            raise ValueError("wrong number of parts")
        if not all(isinstance(part, str) for part in parts):
            raise TypeError("cursor parts are not text")
        return [_storable(part) for part in parts]
    except Exception as exc:
        raise _invalid(exc) from exc


def invalid_cursor(exc: Exception | None = None) -> ValidationFailed:
    """The answer to a cursor whose parts do not parse (422 `validation_failed`)."""
    return _invalid(exc)


def id_page[T](rows: list[T], limit: int, key: Callable[[T], uuid.UUID]) -> Page[T]:
    """`rows` were fetched with `limit + 1`: the extra row tells whether there is more."""
    items = rows[:limit]
    more = len(rows) > limit
    return Page[T](items=items, next_cursor=encode_id_cursor(key(items[-1])) if more else None)

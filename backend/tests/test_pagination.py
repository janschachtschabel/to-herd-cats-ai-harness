import base64
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from uuid_utils.compat import uuid7

from app.core.errors import ValidationFailed
from app.core.pagination import (
    PageParams,
    decode_cursor,
    decode_id_cursor,
    decode_score_cursor,
    encode_cursor,
    encode_id_cursor,
    encode_score_cursor,
)


def test_cursor_round_trip():
    ts, id_ = datetime(2026, 11, 12, tzinfo=UTC), uuid7()
    assert decode_cursor(encode_cursor(ts, id_)) == (ts, id_)


def test_invalid_cursor_is_422():
    with pytest.raises(ValidationFailed):
        decode_cursor("not-a-cursor")


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_is_bounded(limit):
    with pytest.raises(ValidationError):
        PageParams(limit=limit)


def test_id_cursor_round_trip():
    id_ = uuid7()
    assert decode_id_cursor(encode_id_cursor(id_)) == id_


@pytest.mark.parametrize("cursor", ["not-a-cursor", "", "AAAA"])
def test_invalid_id_cursor_is_422(cursor):
    with pytest.raises(ValidationFailed):
        decode_id_cursor(cursor)


def test_score_cursor_round_trip():
    id_ = uuid7()
    for score in (0.0, 1.0000001, 0.1 + 0.2, 123456.789):
        assert decode_score_cursor(encode_score_cursor(score, id_)) == (score, id_)


def _raw(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "raw",
    [
        json.dumps([float("nan"), str(uuid7())]),
        f'[1e999, "{uuid7()}"]',
        f'[-Infinity, "{uuid7()}"]',
        json.dumps([True, str(uuid7())]),
        json.dumps(["1", str(uuid7())]),
        json.dumps([1, 2]),
        f'[{"9" * 5000}, "{uuid7()}"]',
    ],
)
def test_invalid_score_cursor_is_422(raw):
    with pytest.raises(ValidationFailed):
        decode_score_cursor(_raw(raw))

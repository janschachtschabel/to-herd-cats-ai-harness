from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from uuid_utils.compat import uuid7

from app.core.errors import ValidationFailed
from app.core.pagination import PageParams, decode_cursor, encode_cursor


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

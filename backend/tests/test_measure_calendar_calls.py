"""The measurement records a refused call instead of ending (review M10 task 3c,
R3c-3): the gated cases call `list_window` and the expansion directly, so a 422
`calendar.window_too_dense` there is a call with status 422, as it is through the
route, and the report counts it. No database: the session is a stand-in."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest

from app.core.errors import ValidationFailed
from app.modules.calendars import expansion
from scripts.measure_calendar import Bench, Queries
from scripts.measure_calendar_report import Call


class _Session:
    def __init__(self) -> None:
        self.ended: list[str] = []

    async def commit(self) -> None:
        self.ended.append("commit")

    async def rollback(self) -> None:
        self.ended.append("rollback")


class _Database:
    def __init__(self) -> None:
        self.session = _Session()

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[_Session]:
        yield self.session

    def session_factory(self) -> Any:
        return self._session()


@pytest.mark.parametrize(
    "refusal",
    [ValidationFailed(code="calendar.window_too_dense"), expansion.TooDense()],
    ids=["window", "expansion"],
)
async def test_a_refused_call_is_recorded_with_its_status(refusal: Exception) -> None:
    database = _Database()
    bench = Bench(database, Queries())  # type: ignore[arg-type]

    async def work(_session: Any) -> Call:
        raise refusal

    call = await bench.timed(work)
    assert (call.status, call.work, call.occurrences) == (422, None, None)
    assert database.session.ended == ["rollback"]


async def test_another_failure_still_ends_the_run() -> None:
    bench = Bench(_Database(), Queries())  # type: ignore[arg-type]

    async def work(_session: Any) -> Call:
        raise ValidationFailed(code="calendar.window_out_of_range")

    with pytest.raises(ValidationFailed):
        await bench.timed(work)

"""Which archives stay (plan M9 decision 7): grandfather-father-son, the newest of each
of the last days, then of the weeks before, then of the months before; always the
newest good archive; failed archives never count."""

from datetime import UTC, datetime, timedelta

from app.ops.retention import ArchiveInfo, KeepRule, keep_set

NOW = datetime(2026, 11, 15, 3, 0, tzinfo=UTC)
RULE = KeepRule(daily=7, weekly=4, monthly=6)


def _daily(days: int, *, failed: frozenset[int] = frozenset()) -> list[ArchiveInfo]:
    """One archive per day at 02:30 UTC, today first; `failed` are day offsets."""
    return [
        ArchiveInfo(
            name=f"herd-{(NOW - timedelta(days=d)):%Y%m%d}T023000Z-0.1.0.tar",
            created_at=(NOW - timedelta(days=d)).replace(hour=2, minute=30),
            ok=d not in failed,
        )
        for d in range(days)
    ]


def _day(name: str) -> str:
    return name.split("-")[1][:8]


def test_keep_set_grandfather_father_son() -> None:
    archives = _daily(240)
    kept = keep_set(archives, RULE)
    assert len(kept) == 7 + 4 + 6
    days = sorted((_day(n) for n in kept), reverse=True)
    # The last seven days, ...
    assert days[:7] == [f"{(NOW - timedelta(days=d)):%Y%m%d}" for d in range(7)]
    # ... then the newest of each of four older ISO weeks, one per week, ...
    weeks = [datetime.strptime(d, "%Y%m%d").isocalendar()[:2] for d in days[7:11]]
    assert len(set(weeks)) == 4
    newer_weeks = {datetime.strptime(d, "%Y%m%d").isocalendar()[:2] for d in days[:7]}
    assert not set(weeks) & newer_weeks
    # ... then the newest of each of six older months.
    months = [d[:6] for d in days[11:]]
    assert len(set(months)) == 6 and not set(months) & {d[:6] for d in days[:11]}
    for month in months:  # the newest archive of its month: the month's last day
        last = max(_day(a.name) for a in archives if _day(a.name).startswith(month))
        assert last in days
    assert archives[0].name in kept


def test_failed_archives_never_count_and_nothing_is_deleted_without_a_new_good_one() -> None:
    archives = _daily(30, failed=frozenset({0, 1, 2}))
    kept = keep_set(archives, RULE)
    assert not {a.name for a in archives if not a.ok} & kept
    # The days that failed are not filled by older archives of the same day: the
    # daily window is the last seven days that have a good archive.
    assert sorted(_day(n) for n in kept)[-7:] == sorted(
        f"{(NOW - timedelta(days=d)):%Y%m%d}" for d in range(3, 10)
    )
    # Only failed archives: nothing is good, nothing is kept (and the caller deletes
    # nothing, `apply_retention` runs only after a good archive).
    assert keep_set(_daily(3, failed=frozenset({0, 1, 2})), RULE) == set()


def test_the_newest_good_archive_stays_even_with_a_rule_of_nothing() -> None:
    archives = _daily(5)
    assert keep_set(archives, KeepRule(0, 0, 0)) == {archives[0].name}

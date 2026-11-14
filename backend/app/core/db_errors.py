"""Database errors by their SQLSTATE, however the driver and SQLAlchemy wrap them.

- Retryable (`40P01` deadlock, `40001` serialization failure): Postgres rolled the
  transaction back whole; running it again may succeed. The API answers 409
  `conflict.retry` (`errors.py`); a run's step is tried once more (`step_host.py`).
- Timed out (`55P03` lock_timeout, `57014` statement_timeout): a transaction that set
  a time limit (`repository.limit_time`) waited or worked longer.
"""

RETRYABLE = frozenset({"40P01", "40001"})
TIMED_OUT = frozenset({"55P03", "57014"})


def sqlstate_of(exc: BaseException) -> str | None:
    """The SQLSTATE of a database error, looked for through a few layers of wrapping."""
    seen: BaseException | None = exc
    for _ in range(5):
        if seen is None:
            break
        state = getattr(seen, "sqlstate", None)
        if isinstance(state, str):
            return state
        seen = seen.__cause__ or getattr(seen, "orig", None)
    return None


def is_retryable(exc: BaseException) -> bool:
    return sqlstate_of(exc) in RETRYABLE


def is_timeout(exc: BaseException) -> bool:
    return sqlstate_of(exc) in TIMED_OUT

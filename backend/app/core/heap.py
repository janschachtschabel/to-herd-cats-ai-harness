"""The process heap after start-up (plan M10 Task 4, the window measurement).

A full collection of CPython's cyclic collector walks every tracked object: in an API
process several hundred thousand made at import and app creation (routes, schemas,
SQLAlchemy mappers) that live as long as the process. Walked again at each full
collection, they cost 200 to 300 ms a time, which a request that happens to trigger
one waits for (the whole week of the calendar window, paged, reached p95 over 300 ms
by this alone). `freeze_startup_heap` collects once and moves what survives into the
permanent generation, which no later collection walks; full collections then cost
about 30 ms. What start-up made and later drops stays allocated, which is little.
"""

import gc


def freeze_startup_heap() -> None:
    """Called once the process has built what it serves, before serving."""
    gc.collect()
    gc.freeze()

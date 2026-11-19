"""The start-up heap is frozen: later full collections do not walk it."""

import gc

from app.core.heap import freeze_startup_heap


def _walked(target: object) -> bool:
    return any(o is target for o in gc.get_objects())


def test_freezing_takes_what_lives_out_of_later_collections() -> None:
    kept: list[list[int]] = [[1]]
    assert _walked(kept)
    try:
        freeze_startup_heap()
        assert gc.get_freeze_count() > 0
        assert not _walked(kept)
    finally:
        gc.unfreeze()
    assert gc.get_freeze_count() == 0

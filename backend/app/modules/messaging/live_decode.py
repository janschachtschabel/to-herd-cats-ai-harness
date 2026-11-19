"""The API processes' side of live delivery (spec 6.4, `live_events.py`): a NOTIFY
payload back to the `LiveEvent` it carries; anything else is dropped."""

import json
import uuid

from app.modules.messaging.live_events import LIVE_NAMES, LiveEvent


def decode(raw: str) -> LiveEvent | None:
    """The event in a NOTIFY payload; None for anything else."""
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("t") not in LIVE_NAMES:
            return None
        keys = ("c", "m", "p", "u", "w", "s", "r", "n", "x", "a", "y", "b", "l", "e")
        ids = {key: _strict_uuid(data.get(key)) for key in keys}
        org_id = _strict_uuid(data.get("o"))
        step = data.get("k")
        if step is not None and (not isinstance(step, int) or isinstance(step, bool)):
            raise TypeError("not a step")
    except (ValueError, TypeError, RecursionError):
        return None
    if org_id is None:
        return None
    return LiveEvent(
        data["t"],
        org_id,
        ids["c"],
        ids["m"],
        ids["p"],
        ids["u"],
        ids["w"],
        ids["s"],
        ids["r"],
        ids["n"],
        step,
        ids["x"],
        ids["a"],
        ids["y"],
        ids["b"],
        ids["l"],
        ids["e"],
    )


def _strict_uuid(value: object) -> uuid.UUID | None:
    """None for null; a UUID for its text; anything else is refused (ValueError)."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("not an id")
    return uuid.UUID(value)

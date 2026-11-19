"""Overlays as the API shows them (plan M10 task 9)."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.modules.calendars.overlays import Overlay, OverlayKind


class OverlayOut(BaseModel):
    """Something the calendar shows beside events, stored nowhere: a ticket's due day
    (`ref` its key), a sprint from its first to its last day, or an automation's next
    term (`at`, on its day in the viewer's zone; `space_id` null in a DM). `ref` is
    what the interface links with: a ticket's key, else the id. `title`: the ticket's
    title, the sprint's name, the automation's agent."""

    kind: OverlayKind
    id: uuid.UUID
    space_id: uuid.UUID | None
    starts_on: date
    ends_on: date
    ref: str
    title: str
    at: datetime | None

    @classmethod
    def of(cls, overlay: Overlay) -> "OverlayOut":
        return cls(
            kind=overlay.kind,
            id=overlay.id,
            space_id=overlay.space_id,
            starts_on=overlay.starts_on,
            ends_on=overlay.ends_on,
            ref=overlay.ref,
            title=overlay.title,
            at=overlay.at,
        )

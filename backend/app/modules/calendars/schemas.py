"""Calendars and the calendar settings as the API takes and shows them."""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator

from app.modules.calendars.models import (
    DEFAULT_TIME_ZONE,
    NAME_MAX,
    TIME_ZONE_MAX,
    Calendar,
    CalendarColor,
)
from app.modules.calendars.settings import CalendarSettings

CalendarName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_MAX)
]
# An IANA zone name; one `tzdata` does not know is 422 `calendar.invalid_time_zone`.
TimeZone = Annotated[str, StringConstraints(min_length=1, max_length=TIME_ZONE_MAX)]


class CalendarOut(BaseModel):
    """`is_default`: made by the system for a personal space („Mein Kalender“) or the
    general space; there is at most one per space, and it cannot be archived. `name`
    is null for a default nobody renamed: the interface words it. `time_zone`: the
    zone of a new event that names none."""

    id: uuid.UUID
    space_id: uuid.UUID
    name: str | None
    color: CalendarColor
    is_default: bool
    time_zone: str
    version: int

    @classmethod
    def of(cls, calendar: Calendar) -> "CalendarOut":
        return cls(
            id=calendar.id,
            space_id=calendar.space_id,
            name=calendar.name,
            color=CalendarColor(calendar.color),
            is_default=calendar.is_default,
            time_zone=calendar.time_zone,
            version=calendar.version,
        )


class CalendarCreate(BaseModel):
    """A new calendar of the space (`calendar.moderate`); at most 20 per space (409
    `calendar.limit`)."""

    model_config = ConfigDict(extra="forbid")

    name: CalendarName
    color: CalendarColor = CalendarColor.BLUE
    time_zone: TimeZone = DEFAULT_TIME_ZONE


class CalendarUpdate(BaseModel):
    """Fields left out stay as they are (none can be null)."""

    model_config = ConfigDict(extra="forbid")

    name: CalendarName | None = None
    color: CalendarColor | None = None
    time_zone: TimeZone | None = None
    version: int

    @field_validator("name", "color", "time_zone")
    @classmethod
    def _not_null(cls, value: object) -> object:
        if value is None:  # runs only for fields the client sent
            raise ValueError("cannot be null")
        return value


class CalendarSettingsOut(BaseModel):
    sync_enabled: bool
    version: int

    @classmethod
    def of(cls, found: CalendarSettings) -> "CalendarSettingsOut":
        return cls(sync_enabled=found.sync_enabled, version=found.version)


class CalendarSettingsIn(BaseModel):
    """`sync_enabled`: whether people may connect their own external calendars
    (`calendar.sync`; data leaves the house)."""

    model_config = ConfigDict(extra="forbid")

    sync_enabled: bool
    version: int

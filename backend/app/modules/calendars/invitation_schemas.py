"""Attendees and answers as the API takes and shows them (plan M10 task 4)."""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.modules.calendars.attendee_lists import Delivery, Invitee, Kind, delivery_of
from app.modules.calendars.attendee_models import (
    EMAIL_MAX,
    MAX_ATTENDEES,
    NAME_MAX,
    AttendeeRole,
    CalendarEventAttendee,
    Response,
)
from app.modules.calendars.attendee_repository import Listed


class AttendeeIn(BaseModel):
    """A person (`type` `user`) or agent (`agent`) of the system by `id`, or an address
    (`email`, with an optional display `name`)."""

    model_config = ConfigDict(extra="forbid")

    type: Kind
    id: uuid.UUID | None = None
    email: Annotated[EmailStr, StringConstraints(max_length=EMAIL_MAX)] | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, max_length=NAME_MAX)] = ""
    role: AttendeeRole = AttendeeRole.REQUIRED

    @model_validator(mode="after")
    def _one_kind(self) -> "AttendeeIn":
        if self.type is Kind.EMAIL:
            if self.email is None or self.id is not None:
                raise ValueError("an address needs `email` and no `id`")
        elif self.id is None or self.email is not None or self.name:
            raise ValueError("a person or agent needs `id` and nothing else")
        return self

    def invitee(self) -> Invitee:
        return Invitee(self.type, self.id, self.email, self.name, self.role)


class AttendeesIn(BaseModel):
    """The whole list of attendees (at most 100) at the event's `version` read."""

    model_config = ConfigDict(extra="forbid")

    version: int
    attendees: list[AttendeeIn] = Field(max_length=MAX_ATTENDEES)


class AttendeesSetOut(BaseModel):
    """The event's version after the change."""

    version: int


class AttendeeOut(BaseModel):
    """`principal_id` for a person or agent, `email` for an address (a person's
    address is never shown); `name` the person's, agent's or the address's display
    name. `delivery`: `internal` (the activity view), `not_sent` (an address: pass the
    event's `.ics` on)."""

    id: uuid.UUID
    type: Kind
    principal_id: uuid.UUID | None
    email: str | None
    name: str
    role: AttendeeRole
    response: Response
    delivery: Delivery

    @classmethod
    def of(cls, attendee: CalendarEventAttendee, name: str) -> "AttendeeOut":
        return cls(
            id=attendee.id,
            type=Kind(attendee.principal_type or Kind.EMAIL),
            principal_id=attendee.principal_id,
            email=attendee.email,
            name=name,
            role=AttendeeRole(attendee.role),
            response=Response(attendee.response),
            delivery=delivery_of(attendee),
        )

    @classmethod
    def listed(cls, row: Listed) -> "AttendeeOut":
        return cls.of(row.attendee, row.name)


class ResponseIn(BaseModel):
    """An answer (`accepted`, `tentative` or `declined`) at the event's `version`
    read."""

    model_config = ConfigDict(extra="forbid")

    response: Response
    version: int

    @model_validator(mode="after")
    def _an_answer(self) -> "ResponseIn":
        if self.response is Response.NEEDS_ACTION:
            raise ValueError("an answer is accepted, tentative or declined")
        return self

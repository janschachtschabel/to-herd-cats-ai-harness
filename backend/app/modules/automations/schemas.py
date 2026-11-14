"""Automations as the API takes and shows them (plan M7 decisions 4, 12 and 14).

The schedule is one object per kind (`kind` tells which): bounds beyond the types are
the term checks' (`schedule.py`), so a refusal names its reason
(`automation.too_frequent`, `automation.invalid_cron`, ...). The place is where the
results go: the owner's DM with the agent (opened if new), a channel, or a ticket's
thread (by the ticket's number; opened if new).
"""

import uuid
from datetime import datetime, time
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.modules.agents.models import RunState, StopReason
from app.modules.automations.models import (
    DEFAULT_QUIET_SECONDS,
    MAX_INSTRUCTION_CHARS,
    MAX_ZONE_CHARS,
    AutomationKind,
    AutomationState,
    EventType,
    FiringOutcome,
    PausedReason,
)
from app.modules.automations.terms import MAX_CRON_CHARS
from app.modules.tickets.models import TicketKind

Instruction = Annotated[str, Field(min_length=1, max_length=MAX_INSTRUCTION_CHARS)]
Zone = Annotated[str, Field(min_length=1, max_length=MAX_ZONE_CHARS)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OnceIn(_In):
    kind: Literal["once"]
    at: AwareDatetime  # after now (422 `automation.in_the_past`)


class RecurringIn(_In):
    kind: Literal["recurring"]
    cron: Annotated[str, Field(max_length=MAX_CRON_CHARS)]  # five fields
    time_zone: Zone  # an IANA name


class HeartbeatIn(_In):
    kind: Literal["heartbeat"]
    interval_minutes: int  # 15 to 1,440
    active_days: Annotated[list[int], Field(min_length=1, max_length=7)]  # ISO, 1 = Monday
    active_from: time  # local; `active_until` not after it: past midnight (equal: all day)
    active_until: time
    time_zone: Zone


class EventIn(_In):
    kind: Literal["event"]
    event_type: EventType
    quiet_seconds: Annotated[int, Field(ge=60, le=86_400)] = DEFAULT_QUIET_SECONDS
    filter_tag_id: uuid.UUID | None = None  # `ticket.created` only
    filter_ticket_kind: TicketKind | None = None  # `ticket.created` only


ScheduleIn = Annotated[OnceIn | RecurringIn | HeartbeatIn | EventIn, Field(discriminator="kind")]


class DmPlaceIn(_In):
    type: Literal["dm"]


class ChannelPlaceIn(_In):
    type: Literal["channel"]
    conversation_id: uuid.UUID


class TicketPlaceIn(_In):
    type: Literal["ticket"]
    ticket_number: int


PlaceIn = Annotated[DmPlaceIn | ChannelPlaceIn | TicketPlaceIn, Field(discriminator="type")]


class AutomationCreate(_In):
    agent_id: uuid.UUID
    place: PlaceIn
    instruction: Instruction
    schedule: ScheduleIn


class AutomationUpdate(_In):
    """Only its owner; the kind stays (422 `automation.kind_immutable`); a new schedule
    computes the next term anew."""

    version: int
    instruction: Instruction | None = None
    schedule: ScheduleIn | None = None


class PreviewIn(_In):
    schedule: ScheduleIn


class PreviewOut(BaseModel):
    terms: list[datetime]  # the next five (a `once`: its instant; an event rule: none)


class VersionIn(_In):
    version: int


class PlaceOut(BaseModel):
    type: Literal["dm", "channel", "ticket"]
    conversation_id: uuid.UUID
    space_id: uuid.UUID | None  # a DM: none
    name: str | None  # a channel's
    ticket_number: int | None  # a ticket's thread


class NamedOut(BaseModel):
    id: uuid.UUID
    name: str | None  # None: gone


class LastRunOut(BaseModel):
    """The latest term: how it went (`outcome`), its run and how that ended."""

    firing_id: uuid.UUID
    due_at: datetime
    fired_at: datetime
    outcome: FiringOutcome
    heartbeat_ok: bool
    run_id: uuid.UUID | None
    run_state: RunState | None
    stop_reason: StopReason | None


class AbilitiesOut(BaseModel):
    """What the caller may do with it now (`abilities.py`): the same rules the actions
    enforce."""

    edit: bool
    pause: bool
    resume: bool
    delete: bool
    run: bool
    take_over: bool


class AutomationOut(BaseModel):
    """`abilities`: what the caller may do with it now. `upcoming`: its next terms from
    now (none for an event rule, or once done). `redacted`: the caller sees it but
    may not read its place, so `instruction`, `place.name` and `place.ticket_number`
    are null (`words.py`)."""

    id: uuid.UUID
    kind: AutomationKind
    state: AutomationState
    paused_reason: PausedReason | None
    version: int
    instruction: str | None
    redacted: bool
    agent: NamedOut
    owner: NamedOut
    place: PlaceOut
    next_due_at: datetime | None
    cron: str | None
    time_zone: str | None
    interval_minutes: int | None
    active_days: list[int] | None
    active_from: time | None
    active_until: time | None
    event_type: EventType | None
    quiet_seconds: int | None
    filter_tag_id: uuid.UUID | None
    filter_ticket_kind: TicketKind | None
    last_run: LastRunOut | None
    upcoming: list[datetime]
    abilities: AbilitiesOut


class FiringOut(BaseModel):
    """One term of the log: how it went, the run it started, whether a heartbeat's
    run answered `HEARTBEAT_OK` (nothing delivered)."""

    id: uuid.UUID
    due_at: datetime
    fired_at: datetime
    outcome: FiringOutcome
    run_id: uuid.UUID | None
    heartbeat_ok: bool

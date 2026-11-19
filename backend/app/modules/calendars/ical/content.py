"""What an event says besides its time, read from its properties (plan M10 decisions 5,
7, 8 and 10): texts stay plain text (HTML in DESCRIPTION or X-ALT-DESC is never
interpreted), attendees are addresses, alarms become minutes before the start.

- STATUS: CONFIRMED, TENTATIVE, CANCELLED; anything else is confirmed.
- CLASS: PUBLIC (or none) is `default`; PRIVATE, CONFIDENTIAL and any other value are
  `private` (RFC 5545 3.8.1.3: an unknown class is treated as private).
- TRANSP: OPAQUE is busy, TRANSPARENT free; none: busy unless all-day (decision 3).
- ATTENDEE: a `mailto:` address, its CN, ROLE (OPT- and NON-PARTICIPANT are optional)
  and PARTSTAT (DELEGATED and others: needs action); one per address, at most 100.
- SEQUENCE: a whole number up to 2^31 - 1; a larger one is read as that and counted
  (`ical.sequence_capped`); anything else is 0.
- VALARM: a TRIGGER before the start (or before the end, `RELATED=END`), at most four
  weeks; the three nearest the start, each once.
"""

from collections import Counter
from datetime import timedelta

from app.modules.calendars.ical import lines, problems
from app.modules.calendars.ical.drafts import (
    MAX_ALARM_MINUTES,
    MAX_ALARMS,
    MAX_ATTENDEES,
    MAX_DESCRIPTION,
    MAX_LOCATION,
    MAX_TITLE,
    AttendeeDraft,
    Content,
    Response,
    Role,
    Status,
    Visibility,
)
from app.modules.calendars.ical.problems import Skip

_MAX_SEQUENCE = 2**31 - 1
_SEQUENCE_DIGITS = len(str(_MAX_SEQUENCE))
_RESPONSES = {
    "ACCEPTED": Response.ACCEPTED,
    "TENTATIVE": Response.TENTATIVE,
    "DECLINED": Response.DECLINED,
}


def read(part: lines.Component, *, all_day: bool, notes: Counter[str]) -> Content:
    description = part.first("DESCRIPTION") or part.first("X-ALT-DESC")
    return Content(
        title=_text(part.first("SUMMARY"), MAX_TITLE, notes),
        location=_text(part.first("LOCATION"), MAX_LOCATION, notes),
        description=_text(description, MAX_DESCRIPTION, notes),
        status=status(part),
        visibility=_visibility(part.first("CLASS")),
        busy=_busy(part.first("TRANSP"), all_day),
        sequence=_sequence(part.first("SEQUENCE"), notes),
        attendees=_attendees(part.all("ATTENDEE"), notes),
    )


def status(part: lines.Component) -> Status:
    written = part.first("STATUS")
    value = written.raw.strip().upper() if written else ""
    return (
        Status(value.lower())
        if value in ("CONFIRMED", "TENTATIVE", "CANCELLED")
        else Status.CONFIRMED
    )


def organiser(part: lines.Component) -> str | None:
    return lines.address(part.first("ORGANIZER"))


def alarms(part: lines.Component, duration: timedelta, notes: Counter[str]) -> tuple[int, ...]:
    found: set[int] = set()
    for alarm in part.children:
        if alarm.name != "VALARM":
            continue
        minutes = _minutes_before(alarm.first("TRIGGER"), duration)
        if minutes is None:
            notes[problems.ALARM_UNSUPPORTED] = 1
        else:
            found.add(minutes)
    kept = sorted(found)
    if len(kept) > MAX_ALARMS:
        notes[problems.ALARM_UNSUPPORTED] = 1
    return tuple(kept[:MAX_ALARMS])


def _minutes_before(trigger: lines.Prop | None, duration: timedelta) -> int | None:
    if trigger is None or (trigger.param("VALUE") or "").upper() == "DATE-TIME":
        return None
    try:
        days, exact = lines.duration(trigger.raw)
    except Skip:
        return None
    offset = timedelta(days=days) + exact
    if (trigger.param("RELATED") or "").upper() == "END":
        offset += duration
    before = -offset
    if before < timedelta():
        return None
    minutes = int(before.total_seconds() // 60)
    return minutes if minutes <= MAX_ALARM_MINUTES else None


def _text(prop: lines.Prop | None, limit: int, notes: Counter[str]) -> str:
    if prop is None:
        return ""
    text = lines.clean(prop.text)
    if len(text) > limit:
        notes[problems.TEXT_CUT] = 1
        return text[:limit]
    return text


def _visibility(prop: lines.Prop | None) -> Visibility:
    if prop is None or prop.raw.strip().upper() == "PUBLIC":
        return Visibility.DEFAULT
    return Visibility.PRIVATE


def _busy(prop: lines.Prop | None, all_day: bool) -> bool:
    value = prop.raw.strip().upper() if prop else ""
    if value in ("OPAQUE", "TRANSPARENT"):
        return value == "OPAQUE"
    return not all_day


def _sequence(prop: lines.Prop | None, notes: Counter[str]) -> int:
    """SEQUENCE as written; beyond 2^31 - 1 that (the largest, so a later version stays
    later), counted: its length is compared before any `int()`, which refuses more
    than 4,300 digits (re-check RC7a-8)."""
    value = prop.raw.strip().lstrip("0") if prop else ""
    if not value.isascii() or not value.isdigit():
        return 0
    if len(value) > _SEQUENCE_DIGITS or int(value) > _MAX_SEQUENCE:
        notes[problems.SEQUENCE_CAPPED] = 1
        return _MAX_SEQUENCE
    return int(value)


def _attendees(props: list[lines.Prop], notes: Counter[str]) -> tuple[AttendeeDraft, ...]:
    found: list[AttendeeDraft] = []
    seen: set[str] = set()
    for prop in props:
        email = lines.address(prop)
        if email is None or len(found) >= MAX_ATTENDEES:
            notes[problems.ATTENDEE_DROPPED] = 1
            continue
        if email.lower() in seen:
            continue
        seen.add(email.lower())
        name = lines.one_line(prop.param("CN") or "")[:MAX_TITLE] or None
        role = (prop.param("ROLE") or "").upper()
        found.append(
            AttendeeDraft(
                email=email,
                name=name,
                role=Role.OPTIONAL
                if role in ("OPT-PARTICIPANT", "NON-PARTICIPANT")
                else Role.REQUIRED,
                response=_RESPONSES.get(
                    (prop.param("PARTSTAT") or "").upper(), Response.NEEDS_ACTION
                ),
            )
        )
    return tuple(found)

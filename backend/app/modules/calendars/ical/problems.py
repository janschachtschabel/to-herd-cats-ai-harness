"""What reading leaves out, by code (plan M10 decision 10: "Unlesbares wird gezählt und
im Ergebnis je Code genannt, nie stillschweigend verworfen").

A code that skips an event counts once per skipped event (an override once per
override); a code for something an event keeps without (a cut text, an alarm it cannot
take) counts once per event that keeps it.
"""

UNREADABLE = "ical.unreadable"  # no calendar in the data, or a component never ends
LINE_UNREADABLE = "ical.line_unreadable"  # a content line without a name or value
NOT_AN_EVENT = "ical.not_an_event"  # VTODO, VJOURNAL, VFREEBUSY and others
OVER_LIMIT = "ical.over_limit"  # an event beyond the caller's limit

UID_MISSING = "ical.uid_missing"  # no UID, or one longer than drafts.MAX_UID
DUPLICATE_UID = "ical.duplicate_uid"  # a second series with a UID already read
TIME_INVALID = "ical.time_invalid"  # no or unreadable start, end or duration
TIME_OUT_OF_RANGE = "ical.time_out_of_range"  # outside the years 1900 to 2399
TIME_ZONE_UNKNOWN = "ical.time_zone_unknown"  # no IANA, Windows or matching VTIMEZONE
RRULE_INVALID = "ical.rrule_invalid"
RRULE_UNSUPPORTED = "ical.rrule_unsupported"  # below DAILY, BYHOUR, EXRULE, two RRULEs
OVERRIDE_UNMATCHED = "ical.override_unmatched"  # no series, or no such occurrence
OVERRIDE_UNSUPPORTED = "ical.override_unsupported"  # RANGE=THISANDFUTURE

RRULE_NEVER_MATCHES = "ical.rrule_never_matches"  # read as its start alone
ATTENDEE_DROPPED = "ical.attendee_dropped"  # no mailto address, or beyond the limit
ALARM_UNSUPPORTED = "ical.alarm_unsupported"  # after the start, absolute, too early
TEXT_CUT = "ical.text_cut"  # a title, place or text beyond its length

CODES = frozenset(
    {
        UNREADABLE,
        LINE_UNREADABLE,
        NOT_AN_EVENT,
        OVER_LIMIT,
        UID_MISSING,
        DUPLICATE_UID,
        TIME_INVALID,
        TIME_OUT_OF_RANGE,
        TIME_ZONE_UNKNOWN,
        RRULE_INVALID,
        RRULE_UNSUPPORTED,
        OVERRIDE_UNMATCHED,
        OVERRIDE_UNSUPPORTED,
        RRULE_NEVER_MATCHES,
        ATTENDEE_DROPPED,
        ALARM_UNSUPPORTED,
        TEXT_CUT,
    }
)

# A series' refusal (`recurrence.SeriesInvalid.code`) as the problem it is in a file.
FROM_SERIES = {
    "event.rrule_invalid": RRULE_INVALID,
    "event.rrule_unsupported": RRULE_UNSUPPORTED,
    "event.time_out_of_range": TIME_OUT_OF_RANGE,
    "event.invalid_time": TIME_INVALID,
    "event.invalid_time_zone": TIME_ZONE_UNKNOWN,
}


class Skip(Exception):
    """The component cannot be read; `code` says why."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

"""What we use of `icalendar` beyond its documented surface (review M10 Task 7a, R7a-16):
`pyproject.toml` pins 7.3.x; this fails loudly when an upgrade moves or changes one of
these, before anything else can break quietly."""

from importlib.metadata import version

import icalendar
from icalendar import Timezone, vCalAddress
from icalendar.parser import Contentline, Contentlines, rfc_6868_unescape
from icalendar.parser.property import unescape_backslash
from icalendar.prop import vInline
from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON


def test_the_pinned_version_is_installed() -> None:
    assert version("icalendar").startswith("7.3."), version("icalendar")
    assert icalendar.__version__.startswith("7.3.")


def test_lines_split_into_name_parameters_and_value() -> None:
    """`lines.py`: unfolding, parameters with quotes and RFC 6868 carets, the value as
    written."""
    text = 'ATTENDEE;CN="Do^\'e, J^^n";ROLE=REQ-PARTICIPANT:mailto:a@b.org\r\n'
    text += "SUMMARY:a\\nb\\\\nc\\, d\r\n folded\r\n"
    found = Contentlines.from_ical(text)  # type: ignore[no-untyped-call]
    lines = [line for line in found if line]
    assert all(isinstance(line, Contentline) for line in lines)
    name, params, value = lines[0].raw_parts()
    assert (name, value) == ("ATTENDEE", "mailto:a@b.org")
    assert params["CN"] == 'Do"e, J^n' and params["ROLE"] == "REQ-PARTICIPANT"
    name, params, value = lines[1].raw_parts()
    assert value == "a\\nb\\\\nc\\, dfolded"
    assert unescape_backslash(value) == "a\nb\\nc, dfolded"  # `\n` a break, `\\n` text
    assert rfc_6868_unescape("a^'b^^c^nd") == 'a"b^c\nd'  # `lines._split` (RC7a-7)


def test_a_parameter_quoted_for_a_backslash_is_written() -> None:
    """`writing._attendee`: a per-instance `quote_also` quotes a CN that holds one."""
    address = vCalAddress("mailto:x@y.org")
    address.params.quote_also = {"CN": "\\"}
    address.params["CN"] = "end\\"
    assert address.params.to_ical() == b'CN="end\\"'


def test_the_windows_table_maps_names_to_iana_zones() -> None:
    """`zones.py`: Windows names (`W. Europe Standard Time`) and the table's values."""
    assert WINDOWS_TO_OLSON["W. Europe Standard Time"] == "Europe/Berlin"
    assert WINDOWS_TO_OLSON["Eastern Standard Time"] == "America/New_York"


def test_what_writing_builds_on() -> None:
    """`writing.py` and `vtimezone_out.py`: `vInline` writes a value as it is,
    `Timezone.from_tzinfo` takes our own `ZoneInfo` and a span."""
    assert vInline("FREQ=DAILY;COUNT=3").to_ical() == b"FREQ=DAILY;COUNT=3"
    assert callable(Timezone.from_tzinfo)

"""What `tzdata`'s names say, for choosing among zones that fit a file's VTIMEZONE
(`zones`, re-check M10 Task 7a, RC7a-10): which names are links kept for old or merged
zones (`Asia/Calcutta` → `Asia/Kolkata`, `backward`), the order zones are preferred in,
and which zone a TZID or `X-LIC-LOCATION` names.

The order (`ranks`): canonical zones of the Windows table (one well-known city per
region), then other canonical zones of a region (`Europe/…`, `Asia/…`), then links,
then the rest (`Etc/…`, `CET`, `UTC`); within a group by name. A link names its
canonical zone: a location `Asia/Calcutta` or a TZID that says "Chongqing" names
`Asia/Kolkata` or `Asia/Shanghai`, never the link itself.

Links are the `L` lines of `tzdata.zi`, read where `zoneinfo` reads its zones (the
first `zoneinfo.TZPATH` directory that has one, else the `tzdata` package); none found,
there are none, and every name counts as canonical.
"""

import re
import zoneinfo
from functools import lru_cache
from importlib import resources
from pathlib import Path

from icalendar.timezone.windows_to_olson import WINDOWS_TO_OLSON

from app.modules.calendars import zones

# Areas whose names are a city, never a link kept for old names (`US/Eastern`).
_AREAS = frozenset(
    {"Africa", "America", "Antarctica", "Arctic", "Asia", "Atlantic", "Australia"}
    | {"Europe", "Indian", "Pacific"}
)
_NOT_LETTERS = re.compile(r"[^a-z]+")


def _tzdata_zi() -> str:
    for root in zoneinfo.TZPATH:
        path = Path(root) / "tzdata.zi"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    try:
        return resources.files("tzdata").joinpath("zoneinfo", "tzdata.zi").read_text("utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        return ""


@lru_cache(maxsize=1)
def links() -> dict[str, str]:
    """Every link of `tzdata` and the zone it names."""
    found: dict[str, str] = {}
    for line in _tzdata_zi().splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "L":
            found[parts[2]] = parts[1]
    known = zones.names()
    return {link: target for link, target in found.items() if link in known and target in known}


def _regional(name: str) -> bool:
    return name.split("/")[0] in _AREAS and "/" in name


@lru_cache(maxsize=1)
def ranks() -> dict[str, tuple[int, int]]:
    """Every zone's group (see the module) and its place in the order of trial."""
    known, linked = zones.names(), links()
    canonical = {name for name in known - set(linked) if _regional(name)}
    windows = sorted(set(WINDOWS_TO_OLSON.values()) & canonical)
    regional = sorted(canonical - set(windows))
    linking = sorted(name for name in linked if _regional(name))
    rest = sorted(known - canonical - set(linking))
    groups = ((0, windows), (1, regional), (2, linking), (3, rest))
    ordered = [(group, name) for group, names in groups for name in names]
    return {name: (group, index) for index, (group, name) in enumerate(ordered)}


def _city(name: str) -> str:
    return f" {_NOT_LETTERS.sub(' ', name.rpartition('/')[2].lower()).strip()} "


@lru_cache(maxsize=1)
def _cities() -> dict[str, tuple[str, ...]]:
    """Each canonical regional zone's city, and its links' (`Asia/Kolkata`: kolkata,
    calcutta), each between spaces."""
    found: dict[str, list[str]] = {}
    for name, (group, _) in ranks().items():
        if group < 2:
            found.setdefault(name, []).append(_city(name))
    for link, target in links().items():
        if _regional(link) and target in found:
            found[target].append(_city(link))
    return {name: tuple(cities) for name, cities in found.items()}


def words(tzid: str) -> str:
    """The TZID's words, each between spaces (`(UTC+01:00) Amsterdam, Berlin, …`)."""
    return f" {_NOT_LETTERS.sub(' ', tzid.lower()).strip()} "


def named(tzid_words: str, location: str | None, name: str) -> bool:
    """Whether a definition names the canonical zone `name`: its `X-LIC-LOCATION`
    (or a link to it), or its city or a link's in the TZID (its `words`)."""
    if location is not None and links().get(location, location) == name:
        return True
    return any(city in tzid_words for city in _cities().get(name, ()))

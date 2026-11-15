"""License gate: every runtime dependency must carry an allowed license.

    uv export --frozen --no-dev --no-hashes --no-emit-project > runtime.txt
    uv run python scripts/check_licenses.py python runtime.txt
    uv run python scripts/check_licenses.py npm ../frontend/package-lock.json

Python packages are looked up in the running environment (License-Expression, then
License, then the trove classifiers); npm packages come from the lock file, dev-only
packages left out. Exit code 1 lists every package whose license is not allowed.
"""

import json
import re
import sys
from collections.abc import Iterator
from email.message import Message
from importlib import metadata
from pathlib import Path

# CLAUDE.md "Dependencies"; spec decision E2.
ALLOWED = frozenset(
    {
        "MIT",
        "MIT-0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "0BSD",
        "Apache-2.0",
        "ISC",
        "PostgreSQL",
        "PSF-2.0",
        "Python-2.0",
        "MPL-2.0",
        "Unlicense",
        "OFL-1.1",
        "BlueOak-1.0.0",
        "CC0-1.0",
    }
)
_ALLOWED_LOWER = {name.lower() for name in ALLOWED}

# Free text seen in `License:` fields and trove classifiers, mapped to SPDX ids.
ALIASES = {
    "mit license": "MIT",
    "3-clause bsd license": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "apache software license": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "isc license (iscl)": "ISC",
    "isc license": "ISC",
    "mozilla public license 2.0 (mpl 2.0)": "MPL-2.0",
    "the unlicense (unlicense)": "Unlicense",
    "python software foundation license": "PSF-2.0",
    "postgresql license": "PostgreSQL",
    "gnu general public license v2 (gplv2)": "GPL-2.0-only",
    "gnu general public license v3 (gplv3)": "GPL-3.0-only",
    "gnu lesser general public license v3 (lgplv3)": "LGPL-3.0-only",
}
_SPDX_ID = re.compile(r"^[A-Za-z0-9.+-]+$")
_OPERATORS = {"AND", "OR", "WITH"}


def _tokens(expression: str) -> list[str]:
    return re.findall(r"\(|\)|[^\s()]+", expression)


def _evaluate(tokens: list[str]) -> bool:
    """SPDX expression: OR needs one allowed side, AND both; WITH keeps the base."""
    position = 0

    def peek() -> str | None:
        return tokens[position] if position < len(tokens) else None

    def take() -> str:
        nonlocal position
        if position >= len(tokens):
            raise ValueError("unexpected end")
        position += 1
        return tokens[position - 1]

    def atom() -> bool:
        part = take()
        if part == "(":
            value = either()
            if take() != ")":
                raise ValueError("missing )")
            return value
        if part == ")" or part.upper() in _OPERATORS or not _SPDX_ID.match(part):
            raise ValueError(f"unexpected {part}")
        value = part.lower() in _ALLOWED_LOWER
        if (peek() or "").upper() == "WITH":
            take()
            take()  # the exception only grants more
        return value

    def both() -> bool:
        value = atom()
        while (peek() or "").upper() == "AND":
            take()
            value = atom() and value
        return value

    def either() -> bool:
        value = both()
        while (peek() or "").upper() == "OR":
            take()
            value = both() or value
        return value

    result = either()
    if position != len(tokens):
        raise ValueError("trailing tokens")
    return result


def allowed(expression: str) -> bool:
    """True when the SPDX expression is satisfiable with allowed licenses only."""
    try:
        return bool(expression.strip()) and _evaluate(_tokens(expression))
    except ValueError:
        return False


def _spdx(text: str) -> str | None:
    """`text` as an SPDX expression, via the aliases; None if it is neither."""
    text = text.strip()
    if text.lower() in ALIASES:
        return ALIASES[text.lower()]
    tokens = _tokens(text)
    if tokens and all(t in "()" or t.upper() in _OPERATORS or _SPDX_ID.match(t) for t in tokens):
        return text
    return None


def python_license(meta: Message) -> str:
    """The license of an installed distribution as an SPDX expression ("" if none)."""
    if expression := meta.get("License-Expression"):
        return str(expression).strip()
    field = str(meta.get("License") or "").strip()
    if field and "\n" not in field and (spdx := _spdx(field)):
        return spdx
    names = [
        str(c).split("::")[-1].strip()
        for c in meta.get_all("Classifier") or []
        if str(c).startswith("License ::")
    ]
    licenses = [ALIASES.get(n.lower(), "LicenseRef-" + re.sub(r"\W+", "-", n)) for n in names]
    if licenses:
        return " OR ".join(dict.fromkeys(licenses))
    return field.splitlines()[0] if field else ""


def requirement_names(export: str) -> list[str]:
    """Package names from `uv export` output whose markers apply here."""
    from packaging.markers import Marker  # a runtime dependency of the backend

    names = []
    for line in export.splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-")):
            continue
        requirement, _, marker = line.partition(";")
        if marker.strip() and not Marker(marker.strip()).evaluate():
            continue
        names.append(re.split(r"[=<>!~\[ ]", requirement.strip(), maxsplit=1)[0].lower())
    return names


def check_python(names: list[str]) -> tuple[int, list[tuple[str, str]]]:
    problems = []
    for name in names:
        try:
            dist = metadata.distribution(name)
        except metadata.PackageNotFoundError:
            problems.append((name, "not installed"))
            continue
        expression = python_license(dist.metadata)  # type: ignore[arg-type]
        if not allowed(expression):
            problems.append((f"{name}=={dist.version}", expression))
    return len(names), problems


def _npm_packages(lock: dict[str, object]) -> Iterator[tuple[str, dict[str, object]]]:
    packages = lock.get("packages")
    if not isinstance(packages, dict):
        raise ValueError("package-lock.json without `packages` (lockfileVersion >= 2 needed)")
    for path, entry in packages.items():
        if path and isinstance(entry, dict) and not entry.get("dev"):
            yield path, entry


def check_npm_lock(path: Path) -> tuple[int, list[tuple[str, str]]]:
    lock = json.loads(path.read_text(encoding="utf-8"))
    checked, problems = 0, []
    for package_path, entry in _npm_packages(lock):
        checked += 1
        name = package_path.rsplit("node_modules/", 1)[-1]
        raw = entry.get("license")
        expression = str(raw.get("type", "")) if isinstance(raw, dict) else str(raw or "")
        if not allowed(expression):
            problems.append((f"{name}@{entry.get('version')}", expression))
    return checked, problems


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] not in {"python", "npm"}:
        print(__doc__, file=sys.stderr)
        return 2
    kind, source = argv[1], argv[2]
    if kind == "python":
        text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
        checked, problems = check_python(requirement_names(text))
    else:
        checked, problems = check_npm_lock(Path(source))
    for package, expression in problems:
        print(f"NOT ALLOWED: {package}: {expression or '(no license)'}")
    print(f"{kind}: {checked} runtime packages checked, {len(problems)} not allowed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

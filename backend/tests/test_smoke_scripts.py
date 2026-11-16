"""The smoke scripts that drive Docker (CI's image and restore jobs) run under
`set -o pipefail`. A pipeline that ends in `grep -q` fails there even when the line is
found: grep stops reading at the first match, the command in front of it (`docker
compose exec`, `logs`, `ps`, curl) loses its next write to the closed pipe and exits
non-zero, and pipefail makes that the pipeline's status. The worker's /metrics (over 8
KiB, written in two pieces) failed the SMOKE_NODES run this way (CI run 43837783262:
"worker does not report exactly one fired term" with the counter at 1). So these
scripts read the output whole first and grep the value (`grep -q ... <<<"$value"`)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = [
    ROOT / "deploy" / "compose" / "smoke.sh",
    ROOT / "deploy" / "scripts" / "hostinger-smoke.sh",
    ROOT / "deploy" / "scripts" / "restore-rehearsal.sh",
]
# A single `|` (not `||`) followed by grep whose options include q (-q, -Eq, -qx, -E -q).
PIPED_QUIET_GREP = re.compile(r"(?<!\|)\|(?!\|)\s*grep(?:\s+-[A-Za-z]+)*?\s+-[A-Za-z]*q")


def _commands(script: Path) -> list[str]:
    """The script's commands with continuation lines joined, comments left out."""
    text = script.read_text(encoding="utf-8").replace("\\\n", " ")
    return [line for line in text.splitlines() if not line.lstrip().startswith("#")]


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_no_pipeline_ends_in_a_quiet_grep_under_pipefail(script: Path) -> None:
    assert "set -euo pipefail" in script.read_text(encoding="utf-8")
    piped = [line.strip() for line in _commands(script) if PIPED_QUIET_GREP.search(line)]
    assert piped == [], f"{script.name}: read the output first, then grep -q <<<: {piped}"


def test_the_rule_sees_the_forms_it_forbids() -> None:
    assert PIPED_QUIET_GREP.search("docker compose exec -T worker python -c x | grep -Eq '^a 1$'")
    assert PIPED_QUIET_GREP.search("curl -s url | grep -q 'id=\"root\"'")
    assert PIPED_QUIET_GREP.search("cmd | tail -1 | grep -qx ok")
    assert PIPED_QUIET_GREP.search("cmd | grep -E -q x")
    assert not PIPED_QUIET_GREP.search("grep -Eq '^a 1$' <<<\"$metrics\" || fail x")
    assert not PIPED_QUIET_GREP.search("backed_up || fail x")
    assert not PIPED_QUIET_GREP.search("cmd | grep -E x >/dev/null")

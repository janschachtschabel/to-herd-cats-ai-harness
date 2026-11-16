"""docs/SICHERHEIT.md keeps one row per ASVS 5.0.0 requirement of levels 1 and 2."""

import re
from collections import Counter
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "SICHERHEIT.md"
ROW = re.compile(
    r"^\| (V\d+\.\d+) \| (V\d+\.\d+\.\d+) \| (L[12]) \| [^|]+ \| ([^|]+) \| ([^|]+) \|$"
)
STATUSES = {"erfüllt", "nicht anwendbar", "Lücke"}
# ASVS 5.0.0 (tag v5.0.0): 70 requirements at level 1, 183 at level 2.
LEVEL_COUNTS = {"L1": 70, "L2": 183}


def _rows() -> list[tuple[str, str, str, str, str]]:
    lines = DOC.read_text(encoding="utf-8").splitlines()
    return [m.groups() for line in lines if (m := ROW.match(line))]  # type: ignore[misc]


def test_every_level_one_and_two_requirement_has_exactly_one_row() -> None:
    rows = _rows()
    ids = [row[1] for row in rows]
    assert len(ids) == len(set(ids)), "a requirement appears twice"
    assert Counter(row[2] for row in rows) == LEVEL_COUNTS
    for section, number, *_ in rows:
        assert number.startswith(section + "."), number


def test_every_row_has_a_known_status_and_evidence() -> None:
    for _, number, _, status, evidence in _rows():
        assert status.strip() in STATUSES, number
        assert len(evidence.strip()) >= 5, number


def test_every_gap_names_its_question_and_its_plan_and_the_counts_agree() -> None:
    """Every gap names Jan's question (J3, J7 to J14) and either the task that closes
    it (Task 16, M9b Task 18) or that it stays a documented deviation (Abweichung)."""
    rows = _rows()
    for _, number, _, status, evidence in rows:
        if status.strip() == "Lücke":
            assert re.search(r"\bJ\d+\b", evidence), number
            assert re.search(r"Task 1[68]\b|Abweichung", evidence), number
    counts = Counter(row[3].strip() for row in rows)
    text = DOC.read_text(encoding="utf-8")
    for status, count in counts.items():
        assert f"**{count} {status}**" in text, status

"""Line diffs between two versions of a page (`difflib`), as hunks of equal, deleted
and inserted lines; a changed line is a deletion followed by an insertion."""

import difflib
from dataclasses import dataclass
from typing import Literal

HunkKind = Literal["equal", "insert", "delete"]


@dataclass(frozen=True, slots=True)
class Hunk:
    kind: HunkKind
    lines: list[str]


@dataclass(frozen=True, slots=True)
class Diff:
    from_title: str
    to_title: str
    hunks: list[Hunk]

    @property
    def title_changed(self) -> bool:
        return self.from_title != self.to_title


def diff(old_title: str, old_md: str, new_title: str, new_md: str) -> Diff:
    """CPU-bound for large pages: callers run it off the event loop."""
    old, new = old_md.splitlines(), new_md.splitlines()
    hunks: list[Hunk] = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old, b=new).get_opcodes():
        if tag == "equal":
            hunks.append(Hunk("equal", old[i1:i2]))
            continue
        if tag in ("delete", "replace"):
            hunks.append(Hunk("delete", old[i1:i2]))
        if tag in ("insert", "replace"):
            hunks.append(Hunk("insert", new[j1:j2]))
    return Diff(old_title, new_title, hunks)

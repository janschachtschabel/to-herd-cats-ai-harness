"""The three-way merge of a proposal whose page moved on (plan M6 decision 8): line by
line, the base (the page's content when the proposal was made), the proposed content
and the page's current content. Our own merge over `difflib` (no new dependency).

Lines are the text split at `\\n` and joined again, so the text round-trips exactly
(a final newline is an empty last line). Where both sides left the base alone, it
stays; where one side changed a stretch the other left alone, that change wins; the
same change on both sides counts once; anything else is a conflict region, and then
there is no merged text: the moderator resolves it, nothing is chosen silently.

CPU-bound for large pages: callers run it off the event loop and bound its size.
"""

import difflib
from dataclasses import dataclass, field
from typing import Literal

SegmentKind = Literal["clean", "conflict"]


@dataclass(frozen=True, slots=True)
class Segment:
    """`clean`: merged lines (`lines`); `conflict`: the stretch on each side."""

    kind: SegmentKind
    lines: list[str] = field(default_factory=list)
    base: list[str] = field(default_factory=list)
    proposed: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class Merge:
    segments: list[Segment]

    @property
    def conflicts(self) -> list[Segment]:
        return [s for s in self.segments if s.kind == "conflict"]

    @property
    def clean(self) -> bool:
        return not self.conflicts

    @property
    def text(self) -> str | None:
        """The merged text; None while there are conflicts."""
        if not self.clean:
            return None
        return "\n".join(line for s in self.segments for line in s.lines)


def lines_of(text: str) -> list[str]:
    return text.split("\n")


def merge3(base: str, proposed: str, current: str) -> Merge:
    b, p, c = lines_of(base), lines_of(proposed), lines_of(current)
    out = _Builder()
    ib = ip = ic = 0
    for sb, sp, sc, size in [*_stable(b, p, c), (len(b), len(p), len(c), 0)]:
        _chunk(out, b[ib:sb], p[ip:sp], c[ic:sc])
        out.clean(b[sb : sb + size])
        ib, ip, ic = sb + size, sp + size, sc + size
    return Merge(out.segments)


def _chunk(out: "_Builder", base: list[str], proposed: list[str], current: list[str]) -> None:
    """The stretch between two stable regions."""
    if proposed == base:
        out.clean(current)
    elif current == base or proposed == current:
        out.clean(proposed)
    else:
        out.conflict(base, proposed, current)


def _stable(b: list[str], p: list[str], c: list[str]) -> list[tuple[int, int, int, int]]:
    """Stretches of the base that both sides kept as they are: (base start, proposed
    start, current start, length), in order."""
    ours = _matches(b, p)
    theirs = _matches(b, c)
    found: list[tuple[int, int, int, int]] = []
    i = j = 0
    while i < len(ours) and j < len(theirs):
        ob, op, on = ours[i]
        tb, tc, tn = theirs[j]
        start, end = max(ob, tb), min(ob + on, tb + tn)
        if start < end:
            found.append((start, op + start - ob, tc + start - tb, end - start))
        if ob + on < tb + tn:
            i += 1
        else:
            j += 1
    return found


def _matches(a: list[str], b: list[str]) -> list[tuple[int, int, int]]:
    blocks = difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_matching_blocks()
    return [(m.a, m.b, m.size) for m in blocks if m.size]


class _Builder:
    def __init__(self) -> None:
        self.segments: list[Segment] = []

    def clean(self, lines: list[str]) -> None:
        if not lines:
            return
        if self.segments and self.segments[-1].kind == "clean":
            self.segments[-1].lines.extend(lines)
        else:
            self.segments.append(Segment("clean", lines=list(lines)))

    def conflict(self, base: list[str], proposed: list[str], current: list[str]) -> None:
        self.segments.append(
            Segment("conflict", base=list(base), proposed=list(proposed), current=list(current))
        )

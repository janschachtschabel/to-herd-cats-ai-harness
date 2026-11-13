"""Which kind of ticket may sit below which (plan M4 decision 5).

An epic has no parent; a story may have an epic; a task or a bug an epic or a story.
Parent and child are in the same space (a database trigger backs that up). So the
depth is at most three and a cycle cannot happen: every step up goes to a kind that
is strictly higher (bug/task → story → epic).

Races (review focus 4): whoever sets a parent holds the parent's row (`FOR SHARE`),
whoever changes a kind holds its own row (`FOR UPDATE`) and then reads its children,
so a kind change and a new child under it run one after the other and the second
sees the first.
"""

from collections.abc import Iterable

from app.core.errors import ValidationFailed
from app.modules.tickets.models import TicketKind

ALLOWED_PARENTS: dict[TicketKind, frozenset[TicketKind]] = {
    TicketKind.EPIC: frozenset(),
    TicketKind.STORY: frozenset({TicketKind.EPIC}),
    TicketKind.TASK: frozenset({TicketKind.EPIC, TicketKind.STORY}),
    TicketKind.BUG: frozenset({TicketKind.EPIC, TicketKind.STORY}),
}


def parent_invalid() -> ValidationFailed:
    """The same answer for a parent that does not exist, cannot be seen, is in another
    space, is the ticket itself or is of the wrong kind."""
    return ValidationFailed("Not a possible parent", code="ticket.parent_invalid")


def check_parent(kind: TicketKind, parent_kind: TicketKind | None) -> None:
    if parent_kind is not None and parent_kind not in ALLOWED_PARENTS[kind]:
        raise parent_invalid()


def check_children(kind: TicketKind, child_kinds: Iterable[TicketKind]) -> None:
    """A ticket of `kind` may have children of these kinds."""
    if any(kind not in ALLOWED_PARENTS[child] for child in child_kinds):
        raise ValidationFailed(
            "Its children cannot sit below this kind", code="ticket.kind_invalid"
        )

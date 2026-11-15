"""The personal mark: what a person read through her own connector stays with her
(follow-up to plan M8 task 7; module review M8 2, finding G1). The mark follows the
content and is persisted, never only in a worker's memory.

- **Where content is personal**: a result of the asking person's own connector
  (`external_step.py`, journaled as `read.personal`), and every message a marked run
  writes (its answer, a message into its own conversation, its question):
  `message.personal`. Such a message can exist only where the person is alone with the
  agent, since a marked run writes into its own conversation only there
  (`toolbox/writing.into_own`).
- **When a run becomes marked**: the moment personal content enters its context, and
  that moment is journaled at once, so replay, a resume after a question or a release
  and a take-up after a lost worker keep it:
  - a tool result of the person's own connector (`read.personal` on its event);
  - its history window at its start (`in_window`): a `mark` event (`mark_event`)
    before its first model call, written once;
  - a tool that hands it personal content (`search_past_runs` finding anything of a
    marked run, `read_conversation` returning a marked message): the tool sets
    `Reads.personal` and the host journals `read.personal` with its result.
- **What it holds back** (finding G2): a write that anyone but the person could read
  (a channel, a ticket, a page, a proposal, a memory page, a skill, her own
  conversation where others read along) is not refused: it waits for the asking
  person's release of exactly what would be written (`ReleaseFirst`, noted by
  `toolbox/writing.release_first` and raised by `writing.effect` once nothing else
  refused the call, turned into a release by `step_host.py`; in an
  automation's or an event rule's run the owner releases). What is written after a
  release is not marked: she decided to publish it. Into her own conversation alone
  with the agent no release is needed, and what is written there is marked. The
  run's final answer where others read stays held back (`writing.into_own`), and so
  does a question there; external calls follow `external_step.py`. The draft mark is
  another matter and still refuses (`writing.DRAFTS`).
- **What the model is told** (`sections`): `PRESENT` when its history holds marked
  messages; `PERSONAL_LINES` whenever it may call a tool whose result marks lines
  `(personal) ` (`MARKS_LINES`).
- **When it ends**: a run whose window and tool results hold nothing personal starts
  and stays unmarked. A later run never inherits a mark from an earlier one as such,
  only through content it is given. Since every answer of a marked run is marked, in
  a DM that goes on the mark holds while marked answers are in the window.

Content (`message.body_md`) never goes anywhere else through this: who reads a marked
message is who reads the DM (the person; an admin's audited inspection sees it
withheld, `messaging/inspect.py`).
"""

from collections.abc import Sequence

from app.runtime.context import Turn, window

CONVERSATION = "conversation"  # a `mark` event's source: the run's history window

# The model's instructions when its history holds personal messages (it read none of
# it in this run, unless a tool result says so).
PRESENT = (
    "Some earlier messages of this conversation are marked personal: they hold what the "
    "person read through her own connection, and they are for her alone. You have not "
    "read anything like it in this run unless a tool result says so. Answer her here as "
    "usual. Anything you write where others could read it first waits for her release "
    "of exactly that text."
)
PERSONAL_LINE = "(personal) "  # before a marked message or hit in a tool's result
# The tools whose results may hold such lines, and what the model is told about them
# whenever it is offered one of them (module review M8 3, H4).
MARKS_LINES = frozenset({"read_conversation", "search_past_runs"})
PERSONAL_LINES = (
    "A line that starts with (personal) in a result of read_conversation or "
    "search_past_runs holds what the person read through her own connection: it is for "
    "her alone. Once you get such a line, this run holds it: answer her where you are "
    "alone with her; anything you write where others could read it first waits for her "
    "release of exactly that text."
)


def sections(offered: Sequence[str], present: bool) -> list[str]:
    """What the run's instructions say about the mark: that its history holds personal
    messages (`PRESENT`), and what a personal line means if a tool may give one."""
    told = [PRESENT] if present else []
    return told + ([PERSONAL_LINES] if MARKS_LINES & set(offered) else [])


def in_window(turns: Sequence[Turn]) -> bool:
    """Whether the run's history window (what the model is given) holds a marked
    message."""
    return any(turn.flagged for turn in window(turns))


def mark_event() -> dict[str, object]:
    """The journal fact that the history gave the run personal content: the same
    `read.personal` a connector's result carries, on an event of its own."""
    return {"read": {"personal": True}, "source": CONVERSATION}


class ReleaseFirst(Exception):
    """A write others could read, by a run under the personal mark: the host asks the
    person's release of the call and runs it again once she gave it."""

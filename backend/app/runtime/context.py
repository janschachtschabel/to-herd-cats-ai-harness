"""What a run tells the model before it starts (spec 8.3 point 2, 6.3): the agent's
instructions with the frame rule, the sections its host adds after them (the skills
it may load, its memory: already framed where they hold data), and the conversation
so far, limited by characters
(`history_window`, ported from ai-1): the newest turn always stays, older turns are
dropped whole, oldest first. M5 conversations are DMs with one person, so a turn is
one message: the person's (`person`) or the agent's own answer (`agent`)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart

from app.runtime.untrusted import UNTRUSTED_NOTE

HISTORY_CHARS = 24_000

Messages = list[ModelMessage]  # for callers outside `app/runtime` (no Pydantic AI there)

INSTRUCTION_FRAME = (
    "You are {name}, an assistant of this organisation, in a direct conversation with "
    "one person. Answer in the person's language. Use the tools to look things up in "
    "the wiki and the tickets; say so when you found nothing. {untrusted}\n\n"
    "Your instructions:\n{instructions}"
)


@dataclass(frozen=True, slots=True)
class Turn:
    author: Literal["person", "agent"]
    text: str


def instructions(name: str, agent_instructions: str, sections: Sequence[str] = ()) -> str:
    text = INSTRUCTION_FRAME.format(
        name=name, untrusted=UNTRUSTED_NOTE, instructions=agent_instructions or "-"
    )
    return "\n\n".join([text, *sections])


def window(turns: Sequence[Turn], max_chars: int = HISTORY_CHARS) -> list[Turn]:
    """As many of the newest turns as fit into `max_chars` (at least the newest)."""
    kept: list[Turn] = []
    budget = max_chars
    for turn in reversed(turns):
        if kept and len(turn.text) > budget:
            break
        kept.append(turn)
        budget -= len(turn.text)
    return list(reversed(kept))


def history(turns: Sequence[Turn], instructions_text: str) -> Messages:
    """The windowed conversation as model messages, the instructions on the requests."""
    messages: list[ModelMessage] = []
    for turn in window(turns):
        if turn.author == "agent":
            messages.append(ModelResponse(parts=[TextPart(turn.text)]))
        else:
            messages.append(
                ModelRequest(parts=[UserPromptPart(turn.text)], instructions=instructions_text)
            )
    return messages

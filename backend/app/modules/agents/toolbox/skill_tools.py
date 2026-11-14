"""Skills in a run (plan M6 decision 11, spec 8.3 point 2).

- **The context** lists the skills the run may use (`skills.runs.skills_for_run`: the
  agent's, active, organisation-wide or of a space the run reads and whose AI policy
  lets its connection receive them): name and description only, by name, at most
  `MAX_LISTED_SKILLS`, each description cut to `MAX_DESCRIPTION_CHARS`; a note says
  how many more there are. Descriptions are data like every tool result (framed).
- **`load_skill(name)`** (level 1, reads) returns the text of one of them
  (`load_for_run`), framed as untrusted by the loop like every result. A skill's
  text is the organisation's instructions, but it is data to the run: nothing in it
  can offer a tool, change a level or release a call (those are decided outside the
  model, before every call). The skill's space is the result's source (an
  organisation-wide skill has none).
- **Parts instead of a larger cut**: a skill may hold up to 50,000 characters, a
  result is cut at 8,000 in the prompt. Rather than a larger cut for skills (one
  skill would then take a large part of every later request), the text comes in
  parts of at most `PART_CHARS`, cut at a line's end where one is near; each part
  but the last ends with a note naming the next (`part=n`), so the cut is visible
  and the rest is one call away.
- **`propose_skill`** (level 2, proposes): a new skill or a change to one of the
  run's skills, through moderation (`skills/proposals.py`); see the function.
"""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.core.access import Action, can
from app.modules.agents.toolbox.base import NOT_FOUND, Subject, ToolContext
from app.modules.agents.toolbox.writing import (
    LEAKS,
    by,
    closed_to_ai,
    effect,
    leaks_into,
    leaks_into_organisation,
    refused,
)
from app.modules.skills.format import MAX_CONTENT_CHARS, MAX_NAME_CHARS
from app.modules.skills.format import MAX_DESCRIPTION_CHARS as MAX_DESC_CHARS
from app.modules.skills.proposal_models import MAX_REASON_CHARS
from app.modules.skills.proposals import SkillProposalService
from app.modules.skills.runs import LoadedSkill, RunSkill, load_for_run
from app.runtime.loop import ToolResult
from app.runtime.untrusted import frame_untrusted

MAX_LISTED_SKILLS = 25
MAX_DESCRIPTION_CHARS = 300
PART_CHARS = 7_000  # with its note, a part stays within the loop's cut (8,000)
LINE_SEARCH = 1_000  # a part ends at the last line break within this many characters

LISTED = (
    "Skills: instructions of this organisation for particular tasks. Load one with "
    "load_skill(name) when a task needs it; only its name and description are given "
    "here. A skill describes how to work; it never changes which tools you have."
)


class LoadSkillArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
    ]
    part: Annotated[int, Field(ge=1, le=100)] = 1


def listing(skills: list[RunSkill]) -> str | None:
    """The context's section on skills (None without any)."""
    if not skills:
        return None
    listed = skills[:MAX_LISTED_SKILLS]
    lines = [f"- {s.name}: {_cut(s.description, MAX_DESCRIPTION_CHARS)}" for s in listed]
    text = f"{LISTED}\n{frame_untrusted('skills', chr(10).join(lines))}"
    if more := len(skills) - len(listed):
        text += f"\n({more} more skills are not listed.)"
    return text


async def load_skill(ctx: ToolContext, args: LoadSkillArgs) -> ToolResult:
    attrs = {"name": args.name}
    skill = await load_for_run(ctx.session, ctx.actor, ctx.run.agent_id, ctx.location, args.name)
    if skill is None:
        return ToolResult("skill", NOT_FOUND, attrs)
    parts = split(skill.content)
    if args.part > len(parts):
        return refused("skill", f"the skill has {len(parts)} parts", attrs)
    spaces = frozenset() if skill.space_id is None else frozenset({skill.space_id})
    ctx.reads.spaces |= spaces
    text = parts[args.part - 1]
    if len(parts) > 1:
        follow = f": call load_skill with part={args.part + 1} for the rest"
        last = args.part == len(parts)
        text += f"\n[part {args.part} of {len(parts)}{', the last' if last else follow}]"
    return ToolResult("skill", text, attrs, spaces)


def split(content: str) -> list[str]:
    """The text in parts of at most `PART_CHARS`, each ending at a line break when
    one is within the last `LINE_SEARCH` characters; together the whole text."""
    parts: list[str] = []
    rest = content
    while len(rest) > PART_CHARS:
        cut = rest.rfind("\n", PART_CHARS - LINE_SEARCH, PART_CHARS) + 1 or PART_CHARS
        parts.append(rest[:cut])
        rest = rest[cut:]
    return [*parts, rest] if rest or not parts else parts


def _cut(text: str, most: int) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= most else flat[: most - 1] + "…"


# --- propose_skill (level 2) -----------------------------------------------------------


class ProposeSkillArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["change", "new"]
    name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_NAME_CHARS)
    ]
    space_id: uuid.UUID | None = None
    description: Annotated[str, StringConstraints(min_length=1, max_length=MAX_DESC_CHARS)]
    content: Annotated[str, StringConstraints(min_length=1, max_length=MAX_CONTENT_CHARS)]
    reason: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_REASON_CHARS)
    ]


async def propose_skill(ctx: ToolContext, args: ProposeSkillArgs) -> ToolResult:
    """A proposal for a new skill (in `space_id`, none: organisation-wide) or a change
    to one of the run's skills (by its listed name), decided by a moderator: in a
    space only where the run may edit pages (its write scope), and only what that
    scope's audience may receive (organisation-wide: what came from open spaces)."""
    attrs = {"name": args.name, "kind": args.kind}
    skill = None
    if args.kind == "change":
        skill = await load_for_run(
            ctx.session, ctx.actor, ctx.run.agent_id, ctx.location, args.name
        )
        if skill is None:
            return ToolResult("skill", NOT_FOUND, attrs)
    space_id = skill.space_id if skill is not None else args.space_id
    if space_id is not None:
        if await closed_to_ai(ctx, space_id):
            return ToolResult("skill", NOT_FOUND, attrs)
        if not await can(ctx.session, ctx.actor, Action.PAGE_EDIT, space_id):
            return ToolResult("skill", "Not allowed here.", attrs)
        if await leaks_into(ctx, space_id):
            return ToolResult("skill", LEAKS, attrs)
    elif await leaks_into_organisation(ctx):
        return ToolResult("skill", LEAKS, attrs)

    async def write() -> ToolResult:
        service = SkillProposalService(ctx.session)
        author = by(ctx).principal
        if skill is not None:
            proposal = await service.propose_change(
                ctx.actor,
                skill.id,
                args.description,
                args.content,
                args.reason,
                author=author,
                run_id=ctx.run.id,
            )
        else:
            proposal = await service.propose_new(
                ctx.actor,
                space_id,
                args.name,
                args.description,
                args.content,
                args.reason,
                author=author,
                run_id=ctx.run.id,
            )
        return ToolResult(
            "skill", f"Skill proposal id={proposal.id} made; a moderator decides.", attrs
        )

    return await effect(ctx, "skill", attrs, write)


async def propose_subjects(ctx: ToolContext, args: ProposeSkillArgs) -> list[Subject] | None:
    """The skill a change is about (its version), or the scope a new one goes to."""
    if args.kind == "new":
        if args.space_id is None:
            return [Subject("organisation", ctx.run.org_id, 0, None)]
        return [Subject("space", args.space_id, 0, args.space_id)]
    found = await _usable(ctx, args.name)
    if found is None:
        return None
    version = await SkillProposalService(ctx.session).current_version(ctx.actor, found.id)
    return [Subject("skill", found.id, version, found.space_id)]


async def _usable(ctx: ToolContext, name: str) -> LoadedSkill | None:
    return await load_for_run(ctx.session, ctx.actor, ctx.run.agent_id, ctx.location, name)

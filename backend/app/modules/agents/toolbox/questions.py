"""`ask_user` (level 1; plan M6 decision 3 and task 7): the agent asks the person who
asked the run a question and waits for the answer.

The first call posts the question as a card in the run's conversation (`kind`
`question`, `approvals/cards.py`, with an activity entry for the person) and the run
waits (`Wait`, `HERD_AI_APPROVAL_HOURS`). The answer (`POST /api/questions/{id}/
answer`, only by that person) resumes the run; the same call then finds it and gives
it to the model as its result, framed as untrusted like every result. Nobody
answering in time ends the run with `waiting_timeout`. A run that holds a result of
the person's own connector asks only where the person is alone with the agent
(`writing.into_own_conversation`): others would read the question too; there, a
marked run's question is marked personal (`message.personal`).
"""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.core.models_base import utcnow
from app.modules.agents.approvals import cards
from app.modules.agents.approvals.models import MAX_QUESTION_CHARS, QuestionState, RunQuestion
from app.modules.agents.approvals.repository import WaitedRepository
from app.modules.agents.toolbox.base import ToolContext, Wait
from app.modules.agents.toolbox.writing import into_own_conversation, refusal
from app.modules.messaging.models import MessageKind
from app.runtime.loop import ToolResult

UNASKED = "Nobody to ask here."


class AskUserArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_QUESTION_CHARS),
    ]


async def ask_user(ctx: ToolContext, args: AskUserArgs) -> ToolResult | Wait:
    if ctx.call is None:  # outside a run there is no call to come back to
        return ToolResult("question", UNASKED)
    if why := await into_own_conversation(ctx, ctx.run.conversation_id):
        return refusal("question", why)
    repo = WaitedRepository(ctx.session, ctx.run.org_id)
    found = await repo.for_call(RunQuestion, ctx.run.id, ctx.call.step, ctx.call.id)
    if found is None:
        question = await repo.add(
            RunQuestion(
                org_id=ctx.run.org_id,
                run_id=ctx.run.id,
                step=ctx.call.step,
                call_id=ctx.call.id,
                question=args.question,
                state=QuestionState.PENDING,
                addressed_to=ctx.run.user_id,
                expires_at=cards.until(),
                created_at=utcnow(),
            )
        )
        card = await cards.post(
            ctx,
            MessageKind.QUESTION,
            question.id,
            args.question,
            question.addressed_to,
            personal=ctx.reads.personal,  # only alone with the person (above)
        )
        question.message_id = card.id
        await ctx.session.flush()
        return Wait(question.expires_at)
    if found.state == QuestionState.ANSWERED and found.answer is not None:
        return ToolResult("answer", found.answer, {"from": "person"})
    return Wait(found.expires_at)  # not answered yet (past its time: the sweep ends it)
